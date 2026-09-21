export interface UserProfile {
  id: number;
  name: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  name: string;
  email: string;
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  token: string;
}

export interface ClothingAttributes {
  category: string;
  type: string;
  colour: string;
  secondary_colour?: string | null;
  pattern: string;
  style: string;
  sleeve_type?: string | null;
  formality: number;
  material?: string | null;
  confidence: number;
  color_palette?: string[];
}

export interface ImageAnalysisDraft {
  draft_id: string;
  image_url: string;
  detected_attributes: ClothingAttributes;
  is_confirmed: boolean;
}

export interface WardrobeItem {
  id: number;
  wardrobe_code: string;
  user_id: number;
  image_url: string;
  category: string;
  type: string;
  colour: string;
  secondary_colour?: string | null;
  pattern: string;
  style: string;
  sleeve_type?: string | null;
  formality: number;
  material?: string | null;
  confidence: number;
  attributes_confirmed: boolean;
  created_at: string;
  updated_at: string;
}

export interface WardrobeItemCreate {
  image_path: string;
  category: string;
  type: string;
  colour: string;
  secondary_colour?: string | null;
  pattern: string;
  style: string;
  sleeve_type?: string | null;
  formality: number;
  material?: string | null;
  confidence: number;
  attributes_confirmed: boolean;
}

export interface UserRequirements {
  occasion?: string | null;
  style: string[];
  colour_preferences: string[];
  excluded_colours: string[];
  budget?: number | null;
  requested_categories?: string[];
  requested_types?: string[];
  pattern_preferences?: string[];
  additional_preferences: string[];
}

export interface WardrobeSummaryItem {
  wardrobe_id: string;
  category: string;
  type: string;
  colour: string;
  secondary_colour?: string | null;
  pattern: string;
  style: string;
  sleeve_type?: string | null;
  formality: number;
  material?: string | null;
  image_url?: string | null;
  confidence: number;
}

export interface OutfitRequirements {
  required_categories: string[];
  available_categories: string[];
  missing_categories: string[];
  optional_categories: string[];
}

export interface CompatibilityDetails {
  style: string;
  occasion_suitability: string;
  colour_compatibility: string;
  score: number;
  explanation: string;
}

export interface ConfidenceMetrics {
  overall: number;
  vision?: number | null;
  nlp?: number | null;
}

export interface Agent2SearchRequirement {
  missing_categories: string[];
  style: string[];
  colour: string[];
  pattern?: string[];
  occasion?: string | null;
  budget_remaining?: number | null;
  query_text?: string | null;
}

export interface Agent1OutputContract {
  request_id: string;
  user_requirements: UserRequirements;
  wardrobe: WardrobeSummaryItem[];
  outfit_requirements: OutfitRequirements;
  compatible_items: string[];
  compatibility?: CompatibilityDetails | null;
  confidence: ConfidenceMetrics;
  search_requirements: Agent2SearchRequirement;
}

export interface FashionRequestInput {
  query_text: string;
  occasion?: string | null;
  style?: string | null;
  colour_preference?: string | null;
  budget?: number | null;
}

export interface FashionAnalysisResponse {
  request_id: string;
  timestamp: string;
  input_text: string;
  user_requirements: UserRequirements;
  available_wardrobe: WardrobeSummaryItem[];
  outfit_requirements: OutfitRequirements;
  compatible_items: WardrobeSummaryItem[];
  compatibility?: CompatibilityDetails | null;
  confidence: ConfidenceMetrics;
  search_requirements: Agent2SearchRequirement;
  raw_agent1_contract: Agent1OutputContract;
}

export interface AgentStatus {
  agent: string;
  status: string;
  version: string;
  backend?: string;
  vision_backend?: string;
  llm_provider?: string;
  seed_demo_data?: boolean;
  capabilities: string[];
}

export interface SecurityThreatReport {
  is_safe: boolean;
  risk_score: number;
  attack_category?: string | null;
  detected_indicators: string[];
  sanitized_input: string;
  defensive_action: string;
  explanation: string;
}

export interface PresetAttack {
  id: string;
  name: string;
  prompt: string;
  attack_type: string;
}

export interface ApiErrorBody {
  detail?: string | { code?: string; message?: string } | Array<{ msg?: string }>;
}
