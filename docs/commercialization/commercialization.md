# Commercialization Plan

Required by the brief: pricing model, target users/market, deployment ideas.
Draft here, then move the polished version into the final report.

## Target market
- University students and young professionals (initial focus — matches your
  Sri Lankan context and budget-conscious framing)
- Fashion-conscious, budget-conscious shoppers building out a wardrobe

## Pricing model (draft)

| Tier | Price | Includes |
|---|---|---|
| Free | LKR 0 | Limited monthly recommendations, basic wardrobe upload |
| Premium | LKR ___ / month (TBD) | Unlimited recommendations, wardrobe tracking, advanced personalization, style history |
| Retailer / B2B | Custom | FASHORA recommendation engine embedded in a retailer's own site/app |

## Revenue streams
- Affiliate commission when a recommended product is purchased through a partner link
- Premium subscription (above)
- Retailer partnerships / sponsored visibility — must be clearly marked as
  sponsored to stay consistent with the Responsible AI transparency commitment

## Deployment (draft)
- Prototype: local Docker Compose (see root `docker-compose.yml`)
- Target: containerized services on a cloud provider, Postgres managed instance,
  Chroma or a managed vector DB, HTTPS via reverse proxy/load balancer

_Expand this with real figures and a one-page pitch summary before the mid-eval._
