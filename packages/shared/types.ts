/** Shared TypeScript types between mobile and any future web clients. */

export type ConditionType =
  | 'from_contains'
  | 'subject_contains'
  | 'has_attachment'
  | 'label'
  | 'body_keywords'
  | 'time_window';

export interface RuleCondition {
  type: ConditionType;
  value: string | boolean | string[] | { start: string; end: string; timezone: string };
}

export interface RuleConditions {
  logic: 'AND' | 'OR';
  conditions: RuleCondition[];
}

export type EventStatus = 'proposed' | 'confirmed' | 'dismissed';
export type Urgency = 'low' | 'medium' | 'high';
export type DraftTone = 'formal' | 'friendly' | 'brief';
export type NotificationType = 'RULE_MATCH' | 'EVENT_PROPOSAL' | 'SYSTEM';

export interface EventData {
  title: string | null;
  start_datetime: string | null;
  end_datetime: string | null;
  duration_minutes: number | null;
  location: string | null;
  attendees: string[] | null;
  confidence: number;
}
