"""
API routes for the FASHORA budget & purchase planning service.

Mounted under /budget/* so it never collides with Agent 1 (/api/*) or
Agent 2 (/api/v1/*).

Endpoints:
  POST /budget/optimize            — core combinatorial optimization
  POST /budget/plan-purchases      — adapter: real Agent 1 output + Agent 2 results
  POST /budget/reoptimize          — re-plan after Agent 4 rejection
  POST /budget/evaluate-cost       — lightweight price-list check
  GET  /budget/usage/{user_id}     — monthly quota / tier
  POST /budget/subscription/upgrade|downgrade
  POST /budget/affiliate/track-click
  GET  /budget/affiliate/redirect/{product_id}   (destination allow-listed)
  GET  /budget/affiliate/stats                   (service principals only)
  GET  /budget/affiliate/history/{user_id}
  POST /budget/compare-options     — pandas side-by-side comparison
  GET  /budget/health
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal, get_db
from app.core.config import get_settings
from app.core.security import scrub_pii, validate_tenant_access
from app.services.affiliate_service import (
    AffiliateService,
    get_affiliate_service,
    is_allowed_destination,
)
from app.services.comparison_service import ComparisonService, get_comparison_service
from app.services.llm_explanation_service import get_llm_explanation_service
from app.services.optimizer_service import BudgetOptimizerService, get_optimizer_service
from app.services.usage_service import UsageService, get_usage_service
from shared.schemas.agent2_schemas import RetrievalRequest, RetrievalResponse
from shared.schemas.agent3_schemas import (
    AffiliateClickRequest,
    AffiliateClickResponse,
    AffiliateStatsResponse,
    BudgetOptimizationRequest,
    BudgetOptimizationResponse,
    BudgetSource,
    BudgetStatus,
    CandidateProductItem,
    ComparisonRequest,
    ComparisonResponse,
    CostEvaluationRequest,
    CostEvaluationResponse,
    OptimizationStrategy,
    OutfitOption,
    PlanPurchasesRequest,
    ReoptimizationRequest,
    RetrievalRetryLog,
    SubscriptionUpgradeRequest,
    SubscriptionUpgradeResponse,
    SubscriptionTier,
    UsageStatsResponse,
)

logger = logging.getLogger("budget_routes")
settings = get_settings()

# Indirection so tests can inject a stub transport without patching httpx globally.
_new_async_client = httpx.AsyncClient

budget_router = APIRouter(prefix="/budget", tags=["Budget Optimization"])


# ---------------------------------------------------------------------------
# Shared guards
# ---------------------------------------------------------------------------

def _is_service(principal: Dict[str, Any]) -> bool:
    return bool(principal.get("is_service"))


def _enforce_user_guard(
    principal: Dict[str, Any],
    user_id: Optional[Any],
    usage_svc: UsageService,
    db: Session,
    count_usage: bool = False,
) -> Optional[str]:
    """IDOR check + free-tier quota. Returns the effective user id (or None)."""
    if user_id is not None:
        validate_tenant_access(principal.get("sub"), user_id)

    effective_user = str(user_id) if user_id is not None else (
        None if _is_service(principal) else str(principal.get("sub"))
    )
    if effective_user and not _is_service(principal):
        allowed, msg, used, limit = usage_svc.check_quota(db, effective_user)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=msg)
        if count_usage:
            usage_svc.increment_usage(db, effective_user)
    return effective_user


def _polish_recommended_explanation(
    response: BudgetOptimizationResponse,
    llm_polish: bool,
    occasion: Optional[str] = None,
    style_preferences: Optional[List[str]] = None,
) -> None:
    """Optional Gemini rewrite of the recommended option's narrative text.
    Never touches any numbers; deterministic text stays on any failure."""
    if not llm_polish or not response.recommended_option_id:
        return
    svc = get_llm_explanation_service()
    if svc._client is None:
        return
    for opt in response.options:
        if opt.combination_id == response.recommended_option_id:
            opt.financial_explanation = svc.generate_explanation(
                strategy=opt.strategy,
                selected_products=opt.selected_products,
                cost_breakdown=opt.cost_breakdown,
                relevance_score=opt.relevance_score,
                all_options=response.options,
                occasion=occasion,
                style_preferences=style_preferences,
            )
            return


# ---------------------------------------------------------------------------
# Core optimization
# ---------------------------------------------------------------------------

@budget_router.post(
    "/optimize",
    response_model=BudgetOptimizationResponse,
    summary="Optimize purchase combinations within the user budget",
)
async def optimize_budget(
    request: BudgetOptimizationRequest,
    principal: Dict[str, Any] = Depends(get_current_principal),
    optimizer: BudgetOptimizerService = Depends(get_optimizer_service),
    usage_svc: UsageService = Depends(get_usage_service),
    db: Session = Depends(get_db),
    llm_polish: bool = Query(False, description="Gemini-rewrite the recommended explanation"),
) -> BudgetOptimizationResponse:
    _enforce_user_guard(principal, request.user_id, usage_svc, db, count_usage=True)

    logger.info(scrub_pii(
        f"Budget optimization: request_id='{request.request_id}' "
        f"user='{request.user_id}' budget=USD {request.budget}"
    ))

    response = optimizer.optimize(request)
    _polish_recommended_explanation(response, llm_polish)
    return response


# ---------------------------------------------------------------------------
# Pipeline adapter: Agent 1 output + Agent 2 results -> budget plan
# ---------------------------------------------------------------------------

def _candidates_from_retrieval(
    retrieval: Optional[RetrievalResponse],
    seen_ids: set,
) -> List[CandidateProductItem]:
    """Map Agent 2 ProductResults to optimizer candidates.

    Skips: results with no price (money math must never invent one),
    duplicates already present, and unavailable listings.
    """
    out: List[CandidateProductItem] = []
    if not retrieval:
        return out
    for r in retrieval.results:
        pid = str(r.product_id)
        if pid in seen_ids:
            continue
        if r.price is None or r.price <= 0:
            continue
        if not r.availability:
            continue
        seen_ids.add(pid)
        cat = r.category.value if hasattr(r.category, "value") else str(r.category)
        out.append(
            CandidateProductItem(
                product_id=pid,
                name=r.name,
                category=cat,
                colour=r.colour,
                price=round(float(r.price), 2),
                store=r.store,
                url=str(r.url) if r.url else None,
                relevance_score=r.relevance_score,
                availability=r.availability,
            )
        )
    return out


def _resolve_budget(agent1_output) -> tuple:
    """User-stated budget wins; else the Agent 2 search ceiling; else refuse.

    Never invent a budget silently (unrecognized/misunderstood input must
    surface as an explicit error, per the pipeline's no-fallback policy).
    """
    stated = agent1_output.user_requirements.budget
    if stated:
        return float(stated), BudgetSource.USER_STATED
    ceiling = agent1_output.search_requirements.maximum_price
    if ceiling and ceiling > 0:
        return float(ceiling), BudgetSource.SEARCH_CEILING
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "No budget available: the request stated no budget and the retrieval "
            "brief carries no price ceiling. Ask the user for a budget instead of "
            "assuming one."
        ),
    )


async def _request_cheaper_from_agent2(
    original_auth: Optional[str],
    retrieval_request: RetrievalRequest,
    target_price: float,
    excluded_ids: List[str],
    retry_count: int,
) -> Optional[RetrievalResponse]:
    """One feedback-loop call: Agent 2 /api/v1/search with a lowered ceiling."""
    headers = {"Authorization": original_auth} if original_auth else {}
    payload = retrieval_request.model_copy(
        update={
            "max_price": max(0.01, round(target_price, 2)),
            "is_retry": True,
            "retry_count": min(3, retry_count),
            "excluded_product_ids": sorted(set(excluded_ids)),
        }
    )
    url = f"{settings.AGENT2_BASE_URL.rstrip('/')}/api/v1/search"
    try:
        async with _new_async_client(timeout=settings.AGENT2_SEARCH_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload.model_dump(mode="json"), headers=headers)
        if resp.status_code != 200:
            logger.warning(f"Feedback-loop Agent 2 call failed: HTTP {resp.status_code}")
            return None
        return RetrievalResponse(**resp.json())
    except Exception as e:
        logger.warning(f"Feedback-loop Agent 2 call error: {str(e)[:200]}")
        return None


@budget_router.post(
    "/plan-purchases",
    response_model=BudgetOptimizationResponse,
    summary="Plan purchases from real Agent 1 + Agent 2 outputs",
)
async def plan_purchases(
    body: PlanPurchasesRequest,
    http_request: Request,
    principal: Dict[str, Any] = Depends(get_current_principal),
    optimizer: BudgetOptimizerService = Depends(get_optimizer_service),
    usage_svc: UsageService = Depends(get_usage_service),
    db: Session = Depends(get_db),
    llm_polish: bool = Query(False),
) -> BudgetOptimizationResponse:
    a1 = body.agent1_output

    if a1.outfit_requirements.clarification_needed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                a1.outfit_requirements.clarification_message
                or "Agent 1 needs clarification before a budget can be planned."
            ),
        )

    _enforce_user_guard(principal, body.user_id, usage_svc, db, count_usage=True)

    budget, budget_source = _resolve_budget(a1)
    missing = [c.lower().strip() for c in a1.outfit_requirements.missing_categories]

    # Build per-category candidates from the Agent 2 responses
    candidates: Dict[str, List[CandidateProductItem]] = {}
    seen_ids: set = set()
    skipped_no_price = 0
    for resp_cat, retrieval in body.retrieval_by_category.items():
        if retrieval and retrieval.results:
            skipped_no_price += sum(1 for r in retrieval.results if r.price is None)
        before = len(seen_ids)
        candidates[resp_cat.lower().strip()] = _candidates_from_retrieval(retrieval, seen_ids)
    for cat in missing:
        candidates.setdefault(cat, [])

    opt_req = BudgetOptimizationRequest(
        request_id=a1.request_id,
        user_id=body.user_id if body.user_id is not None else (None if _is_service(principal) else principal.get("sub")),
        budget=budget,
        budget_source=budget_source,
        missing_categories=missing,
        outfit_categories=[
            c.lower().strip() for c in a1.outfit_requirements.required_categories
        ],
        compatible_wardrobe_ids=[str(i) for i in a1.compatible_items],
        preferred_colours=[
            c.lower().strip()
            for c in list(a1.user_requirements.colour_preferences)
            + [
                it.colour
                for it in a1.user_requirements.identified_items
                if it.colour and it.role == "requested"
            ]
            if c and c.strip()
        ],
        excluded_colours=[c.lower().strip() for c in a1.user_requirements.excluded_colours if c],
        requested_styles=[
            s.lower().strip().replace(" ", "_") for s in a1.user_requirements.style if s
        ],
        candidate_products_by_category=candidates,
        available_wardrobe=a1.wardrobe,
        strategy_preference=body.strategy_preference,
        excluded_product_ids=[],
        retrieval_requests_by_category=body.retrieval_requests_by_category,
    )

    response = optimizer.optimize(opt_req)
    retry_log: List[RetrievalRetryLog] = []

    # Feedback loop: ask Agent 2 for cheaper alternatives, re-compute
    original_auth = http_request.headers.get("authorization")
    rounds = 0
    while (
        body.enable_feedback_loop
        and rounds < settings.FEEDBACK_LOOP_MAX_ROUNDS
        and response.status in (BudgetStatus.EXCEEDS_BUDGET, BudgetStatus.PARTIALLY_FEASIBLE)
        and response.feedback_loop_recommendations
        and opt_req.retrieval_requests_by_category
    ):
        rounds += 1
        any_new_products = False
        known_ids_by_cat = {
            cat: {p.product_id for p in items} for cat, items in candidates.items()
        }

        for rec in response.feedback_loop_recommendations:
            cat = rec.category.lower().strip()
            base_req = opt_req.retrieval_requests_by_category.get(cat)
            if base_req is None:
                continue
            if rec.target_max_price <= 0:
                continue

            new_retrieval = await _request_cheaper_from_agent2(
                original_auth=original_auth,
                retrieval_request=base_req,
                target_price=rec.target_max_price,
                excluded_ids=sorted(known_ids_by_cat.get(cat, set()) | seen_ids),
                retry_count=rounds,
            )
            added = _candidates_from_retrieval(new_retrieval, seen_ids)
            if added:
                any_new_products = True
                candidates.setdefault(cat, []).extend(added)
            retry_log.append(
                RetrievalRetryLog(
                    iteration=rounds,
                    category=cat,
                    target_max_price=round(rec.target_max_price, 2),
                    previous_lowest_price=round(rec.current_lowest_price, 2),
                    new_products_found=len(added),
                    notes=rec.suggested_query_notes,
                )
            )

        if not any_new_products:
            break

        opt_req = opt_req.model_copy(
            update={"candidate_products_by_category": {c: list(v) for c, v in candidates.items()}}
        )
        response = optimizer.optimize(opt_req)

    response.retry_log = retry_log
    if retry_log:
        response.notes = (
            (response.notes or "")
            + f" Feedback loop: {rounds} Agent 2 retr{'y' if rounds == 1 else 'ies'} attempted"
            f" for cheaper alternatives ({len({r.category for r in retry_log})} category(ies))."
        )
    if skipped_no_price:
        response.notes = (
            (response.notes or "")
            + f" {skipped_no_price} retrieved listing(s) had no price and were excluded from cost math."
        )

    _polish_recommended_explanation(
        response,
        llm_polish,
        occasion=a1.user_requirements.occasion,
        style_preferences=a1.user_requirements.style,
    )
    return response


# ---------------------------------------------------------------------------
# Re-optimization & cost evaluation
# ---------------------------------------------------------------------------

@budget_router.post(
    "/reoptimize",
    response_model=BudgetOptimizationResponse,
    summary="Re-plan after rejected combinations or a required savings target",
)
async def reoptimize_budget(
    request: ReoptimizationRequest,
    principal: Dict[str, Any] = Depends(get_current_principal),
    optimizer: BudgetOptimizerService = Depends(get_optimizer_service),
    usage_svc: UsageService = Depends(get_usage_service),
    db: Session = Depends(get_db),
) -> BudgetOptimizationResponse:
    _enforce_user_guard(principal, request.user_id, usage_svc, db, count_usage=True)

    effective_budget = request.budget
    if request.target_savings_percentage and request.target_savings_percentage > 0:
        multiplier = 1.0 - (request.target_savings_percentage / 100.0)
        effective_budget = max(1.0, request.budget * multiplier)

    opt_req = BudgetOptimizationRequest(
        request_id=request.request_id,
        user_id=request.user_id,
        budget=effective_budget,
        missing_categories=list(request.candidate_products_by_category.keys()),
        candidate_products_by_category=request.candidate_products_by_category,
        available_wardrobe=request.available_wardrobe,
    )

    response = optimizer.optimize(opt_req)

    filtered: List[OutfitOption] = [
        o for o in response.options if o.combination_id not in request.rejected_combination_ids
    ]
    response.options = filtered
    if filtered:
        best = max(filtered, key=lambda o: o.overall_value_score)
        response.recommended_option_id = best.combination_id
    else:
        response.recommended_option_id = None

    response.notes = (
        f"Re-optimization with effective budget USD {effective_budget:,.2f} "
        f"(target savings: {request.target_savings_percentage or 0:.0f}%). "
        f"Excluded: {request.rejected_combination_ids}."
    )
    return response


@budget_router.post(
    "/evaluate-cost",
    response_model=CostEvaluationResponse,
    summary="Check whether a list of prices fits the budget",
)
async def evaluate_cost(
    request: CostEvaluationRequest,
    principal: Dict[str, Any] = Depends(get_current_principal),
) -> CostEvaluationResponse:
    total = sum(request.product_prices)
    remaining = request.budget - total
    savings_amount = max(0.0, remaining)
    savings_pct = (savings_amount / max(1.0, request.budget)) * 100.0
    return CostEvaluationResponse(
        total_cost=round(total, 2),
        budget_ceiling=round(request.budget, 2),
        budget_remaining=round(remaining, 2),
        is_within_budget=(total <= request.budget),
        savings_percentage=round(savings_pct, 2),
    )


# ---------------------------------------------------------------------------
# Subscription & usage
# ---------------------------------------------------------------------------

@budget_router.get(
    "/usage/{user_id}",
    response_model=UsageStatsResponse,
    summary="Monthly recommendation quota and tier for a user",
)
async def get_usage_stats(
    user_id: str,
    principal: Dict[str, Any] = Depends(get_current_principal),
    usage_svc: UsageService = Depends(get_usage_service),
    db: Session = Depends(get_db),
) -> UsageStatsResponse:
    if not _is_service(principal):
        validate_tenant_access(principal.get("sub"), user_id)
    return UsageStatsResponse(**usage_svc.get_usage_stats(db, user_id))


@budget_router.post(
    "/subscription/upgrade",
    response_model=SubscriptionUpgradeResponse,
    summary="Upgrade a user to Premium tier",
)
async def upgrade_subscription(
    request: SubscriptionUpgradeRequest,
    principal: Dict[str, Any] = Depends(get_current_principal),
    usage_svc: UsageService = Depends(get_usage_service),
    db: Session = Depends(get_db),
) -> SubscriptionUpgradeResponse:
    if not _is_service(principal):
        validate_tenant_access(principal.get("sub"), request.user_id)
    usage_svc.upgrade_to_premium(db, request.user_id)
    logger.info(f"Subscription upgraded: user={request.user_id}")
    return SubscriptionUpgradeResponse(
        user_id=request.user_id,
        tier=SubscriptionTier.PREMIUM,
        message=(
            "Welcome to FASHORA Premium! You now have unlimited recommendations, "
            "wardrobe tracking, and personalised fashion history."
        ),
        monthly_limit=-1,
    )


@budget_router.post(
    "/subscription/downgrade",
    response_model=SubscriptionUpgradeResponse,
    summary="Downgrade a user to Free tier",
)
async def downgrade_subscription(
    request: SubscriptionUpgradeRequest,
    principal: Dict[str, Any] = Depends(get_current_principal),
    usage_svc: UsageService = Depends(get_usage_service),
    db: Session = Depends(get_db),
) -> SubscriptionUpgradeResponse:
    if not _is_service(principal):
        validate_tenant_access(principal.get("sub"), request.user_id)
    usage_svc.downgrade_to_free(db, request.user_id)
    return SubscriptionUpgradeResponse(
        user_id=request.user_id,
        tier=SubscriptionTier.FREE,
        message=f"Reverted to Free tier ({settings.FREE_TIER_MONTHLY_LIMIT} recommendations/month).",
        monthly_limit=settings.FREE_TIER_MONTHLY_LIMIT,
    )


# ---------------------------------------------------------------------------
# Affiliate tracking
# ---------------------------------------------------------------------------

@budget_router.post(
    "/affiliate/track-click",
    response_model=AffiliateClickResponse,
    summary="Record a product link click and return the tracked URL",
)
async def track_affiliate_click(
    request_body: AffiliateClickRequest,
    http_request: Request,
    principal: Dict[str, Any] = Depends(get_current_principal),
    affiliate_svc: AffiliateService = Depends(get_affiliate_service),
    db: Session = Depends(get_db),
) -> AffiliateClickResponse:
    client_ip = http_request.client.host if http_request.client else None
    click = affiliate_svc.record_click(
        db=db,
        product_id=request_body.product_id,
        product_name=request_body.product_name,
        product_url=request_body.product_url,
        store=request_body.store,
        category=request_body.category,
        price_usd=request_body.price_usd,
        user_id=request_body.user_id or principal.get("sub"),
        request_id=request_body.request_id,
        client_ip=client_ip,
    )
    tracked_url = affiliate_svc.build_tracked_url(request_body.product_id, request_body.product_url)
    return AffiliateClickResponse(
        click_id=click.id,
        product_id=click.product_id,
        tracked_url=tracked_url,
        estimated_commission_usd=click.estimated_commission_usd,
        message=(
            f"Click recorded. Estimated commission: "
            f"USD {click.estimated_commission_usd or 0:.2f}"
        ),
    )


@budget_router.get(
    "/affiliate/redirect/{product_id}",
    summary="Tracked redirect to the retailer (allow-listed destinations only)",
)
async def affiliate_redirect(
    product_id: str,
    destination: str = Query(default=""),
):
    if not destination:
        raise HTTPException(status_code=404, detail="No destination URL for this product.")
    if not is_allowed_destination(destination):
        # Open-redirect defense: https + known retailer domains only.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redirect destination is not an allowed retailer URL.",
        )
    return RedirectResponse(url=destination, status_code=302)


@budget_router.get(
    "/affiliate/stats",
    response_model=AffiliateStatsResponse,
    summary="Commission & click analytics (service principals only)",
)
async def affiliate_stats(
    days: int = Query(default=30, ge=1, le=365),
    principal: Dict[str, Any] = Depends(get_current_principal),
    affiliate_svc: AffiliateService = Depends(get_affiliate_service),
    db: Session = Depends(get_db),
) -> AffiliateStatsResponse:
    if not _is_service(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Affiliate analytics require an inter-agent service token.",
        )
    return AffiliateStatsResponse(**affiliate_svc.get_click_stats(db, days=days))


@budget_router.get(
    "/affiliate/history/{user_id}",
    summary="A user's affiliate click history",
)
async def affiliate_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    principal: Dict[str, Any] = Depends(get_current_principal),
    affiliate_svc: AffiliateService = Depends(get_affiliate_service),
    db: Session = Depends(get_db),
):
    if not _is_service(principal):
        validate_tenant_access(principal.get("sub"), user_id)
    return {"user_id": user_id, "clicks": affiliate_svc.get_user_clicks(db, user_id, limit)}


# ---------------------------------------------------------------------------
# Comparison analytics
# ---------------------------------------------------------------------------

@budget_router.post(
    "/compare-options",
    response_model=ComparisonResponse,
    summary="Side-by-side pandas comparison of outfit options",
)
async def compare_options(
    request: ComparisonRequest,
    principal: Dict[str, Any] = Depends(get_current_principal),
    comparison_svc: ComparisonService = Depends(get_comparison_service),
) -> ComparisonResponse:
    ranked = comparison_svc.build_comparison_table(request.options, request.budget)
    cat_break = comparison_svc.build_category_breakdown(request.options)
    savings = comparison_svc.savings_ranking(request.options)
    summary_resp = BudgetOptimizationResponse(
        request_id="compare",
        status=BudgetStatus.WITHIN_BUDGET,
        budget_ceiling=request.budget,
        options=request.options,
    )
    stats = comparison_svc.summary_stats(summary_resp)
    return ComparisonResponse(
        ranked_options=ranked,
        category_breakdown=cat_break,
        savings_ranking=savings,
        summary_stats=stats,
    )


@budget_router.get("/health", summary="Service health")
async def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "service": "budget",
        "version": settings.VERSION,
        "currency": settings.CURRENCY,
        "llm": settings.LLM_PROVIDER,
        "db": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgres",
    }
