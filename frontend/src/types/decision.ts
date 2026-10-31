export type DecisionStatus = "proposed" | "accepted" | "rejected" | "unresolved";

export interface EvidenceReference {
  sourceUrl: string;
  excerpt: string;
}

export interface DecisionSummary {
  id: string;
  summary: string;
  status: DecisionStatus;
  evidence: EvidenceReference[];
}
