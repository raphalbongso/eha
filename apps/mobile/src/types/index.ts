/** EHA TypeScript type definitions. */

// --- Auth ---
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: string;
  email: string;
  name: string;
}

// --- Rules ---
export type ConditionType =
  | 'from_contains'
  | 'subject_contains'
  | 'has_attachment'
  | 'label'
  | 'body_keywords'
  | 'time_window';

export interface RuleCondition {
  type: ConditionType;
  value: string | boolean | string[] | TimeWindow;
}

export interface TimeWindow {
  start: string; // HH:MM
  end: string; // HH:MM
  timezone: string;
}

export interface RuleConditions {
  logic: 'AND' | 'OR';
  conditions: RuleCondition[];
}

export interface Rule {
  id: string;
  name: string;
  conditions: RuleConditions;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RuleCreateRequest {
  name: string;
  conditions: RuleConditions;
  is_active?: boolean;
}

// --- Alerts ---
export interface Alert {
  id: string;
  message_id: string;
  rule_id: string | null;
  rule_name: string | null;
  read: boolean;
  created_at: string;
  subject: string | null;
  from_addr: string | null;
  snippet: string | null;
}

// --- AI / Drafts ---
export interface Summary {
  summary: string;
  action_items: string[];
  urgency: 'low' | 'medium' | 'high';
}

export interface DraftProposal {
  tone: 'formal' | 'friendly' | 'brief';
  subject: string;
  body: string;
}

export interface Draft {
  id: string;
  message_id: string;
  gmail_draft_id: string | null;
  content_preview: string;
  tone: string;
  created_at: string;
}

// --- Events ---
export interface EventData {
  title: string | null;
  start_datetime: string | null;
  end_datetime: string | null;
  duration_minutes: number | null;
  location: string | null;
  attendees: string[] | null;
  confidence: number;
  source_message_id?: string;
}

export type EventStatus = 'proposed' | 'confirmed' | 'dismissed';

export interface ProposedEvent {
  id: string;
  message_id: string;
  event_data: EventData;
  status: EventStatus;
  created_at: string;
}

// --- Devices ---
export interface DeviceRegisterRequest {
  platform: 'ios' | 'android';
  token: string;
  device_id: string;
}

// --- Navigation ---
export type RootStackParamList = {
  Login: undefined;
  Main: undefined;
  EmailDetail: { messageId: string; subject?: string; fromAddr?: string };
  ProposedEvent: { event: ProposedEvent };
};

export type MainTabParamList = {
  Inbox: undefined;
  Rules: undefined;
  Settings: undefined;
};
