export type Municipality = { id: string; name: string; short: string; city: string; color_slot: number }
export type Deadline = { status: 'ontrack' | 'atrisk' | 'late'; due_at: string | null; days: number | null }
export type Explanation = {
  what: string; why: string; next: string; who: string; since: string
  last_event: { action: string; why: string; at: string } | null
}
export type Axis = 'blocked' | 'waiting' | 'running' | 'paused' | 'failed' | 'completed'
export type CaseCard = {
  id: string; municipality: Municipality; process: { id: string; code: string; name: string }
  secretariat: string | null; state: string; state_label: string; axis: Axis; version: number; cycle: number
  ball_owner: string; deadline: Deadline; since: string; explanation: Explanation
}
export type Task = {
  task_id: string; kind: string; client: Municipality; process: { id: string; code: string; name: string }
  case_id: string | null; title: string; why: { code: string; text: string }; since: string
  deadline: Deadline; primary_action: { label: string; route: string }; urgency: number; secretariat: string | null
}
export type Today = { tasks: Task[]; waiting: CaseCard[]; agent: CaseCard[]; counts_by_client: Record<string, number>; generated_at: string }
export type Runtime = { app_env: string; banner: string; ai_mode: string; extraction_simulated: boolean; business_now: string }
export type Me = { id: string; name: string; kind: string; municipality_id: string | null; is_implanter?: boolean }
export type Persona = { id: string; name: string; kind: string; municipality_id: string | null }
export type CaseDetail = CaseCard & {
  ticket: { id: string; title: string; description: string; initial_reply: string; status: string }
  change_requests: { id: string; summary: string; quote: string; clarity: string; feasibility: string; risk: string; disposition: string }[]
  change_set_id: string | null
  approvals: { id: string; role: string; decision: string; actor_id: string; channel: string; rationale: string; candidate_hash: string; at: string; valid: boolean; invalidated_reason: string | null }[]
  interventions: { id: string; code: string; reason: string; needed: string; status: string; resolution: string | null; urgency: number }[]
  next_action: string
}
export type DiffItem = { kind: string; field_id?: string; rule_id?: string; label?: string; attr?: string; before?: unknown; after?: unknown }
export type TestRow = { id: string; name: string; kind: string; inputs: Record<string, unknown>; expected_codes: string[]; requirement: string; reviewed: boolean }
export type ChangeSetDetail = {
  id: string; case_id: string; status: string; candidate_hash: string; short_hash: string; rationale: string
  case_version: number; case_state: string; applied_version_id: string | null; diff: DiffItem[]
  tests: TestRow[]; suite_hash: string; coverage_gaps: string[]
  last_run: { id: string; passed: boolean; stale: boolean; results: { name?: string; passed: boolean; expected?: string[]; actual?: string[]; coverage_gap?: string }[] } | null
  readback_run: { id: string; passed: boolean } | null; open_interventions: number
}
export type TimelineEvent = { seq: number; actor: string; action: string; from: string | null; to: string | null; why: string; at: string }
export type Intervention = { id: string; code: string; reason: string; needed: string; urgency: number; case: CaseCard; since: string }
export type ClientRow = Municipality & { processes: number; not_started: number; active_cases: number; completed: number; target_date: string | null }
export type PortalItem = { case_id: string; process: { code: string; name: string }; deadline: Deadline; state: string; change_set_id: string | null; kind: 'approval' | 'waiting' | 'done' | 'question'; item_id?: string; title: string; why: string }
export type PortalHome = { municipality: Municipality; person: { id: string; name: string }; secretariat: string | null; next_step: PortalItem | null; today: PortalItem[]; waiting: PortalItem[]; done: PortalItem[] }
export type PortalApproval = {
  change_set_id: string; municipality: Municipality; secretariat: string | null; process: { code: string; name: string }
  version_label: string; case_version: number; can_decide: boolean; case_state: string
  changes: { kind: string; text: string }[]; examples: { title: string; when: string; result: string }[]
  why: string; decided: { decision: string; at: string; valid: boolean }[]; deadline: Deadline
}

export type Gap = { id: string; ref: string; question: string; answer_kind: string; options: string[]; topic: string; status: 'open' | 'answered' | 'obsolete' | 'disputed'; blocking: boolean; note: string }
export type RoundItemRow = { id: string; position: number; question: string; status: string; answer_kind: string; options: string[]; due_at: string | null }
export type RoundRow = {
  id: string; seq: number; status: string; revision: number; objective: string; summary: string; grouping_note: string
  recipient: { id: string; name: string }; channels: string[]; sent_at: string | null; reminders_sent: number
  items: RoundItemRow[]; preview: string | null; awaiting_review: boolean
}
export type Msg = {
  id: string; seq: number; channel: 'pylon' | 'whatsapp' | 'portal'; direction: 'in' | 'out'; body: string
  actor: { id: string; name: string } | null; round_id: string | null; substantive: boolean; flagged: boolean
  triage: string | null; mirror: boolean; consolidated: boolean; at: string
  attachments: { id: string; filename: string; content_type: string; size: number; status: string }[]
  derived: { id: string; adapter: string; simulated: boolean; status: string; text: string }[]
}
export type Referral = { id: string; name: string; sector: string; alias: string; topic: string; status: string; from: { id: string; name: string } | null; gaps: string[]; new_actor_id: string | null }
export type Convo = { messages: Msg[]; referrals: Referral[]; decisions: { id: string; kind: string; text: string; actor_id: string; at: string }[] }
export type InboxMsg = { id: string; channel: 'pylon' | 'whatsapp' | 'portal'; body: string; case_id: string; municipality: Municipality; process: { code: string; name: string }; actor: string | null; substantive: boolean; flagged: boolean; triage: string | null; round_id: string | null; at: string; case_state: string }
export type ScenarioStep = { id: string; label: string; type: string; actor?: string; channel?: string; text?: string; expect?: string }
export type Scenario = { id: string; title: string; description: string; process_id: string; mode: string; reply: string; steps: ScenarioStep[] }
export type PortalQuestion = {
  id: string; round_id: string; case_id: string; process: { code: string; name: string }; question: string; why: string
  answer_kind: string; options: string[]; deadline: Deadline; position: number; total: number; demo_hint: string | null
}
export type PortalHomeX = PortalHome & { upcoming: PortalItem[]; daily_budget: number; needs_onboarding: boolean }
export type Onboarding = {
  name: string; secretariat: string | null; municipality: Municipality; preferred_channel: string | null; done: boolean
  processes: { id: string; code: string; name: string; claim: string | null; refer_name: string }[]
}
export type ScheduleClient = Municipality & {
  start: string | null; target: string | null; now: string
  processes: { id: string; code: string; name: string; wave: number; due_at: string | null; deadline: Deadline; case_id: string | null; axis: Axis | 'idle'; state_label: string }[]
}
export type Metrics = {
  evidence_class: string; limitation: string
  processes: { total: number; nao_iniciados: number; com_caso: number }
  cases: { total: number; concluidos: number; em_andamento: number; falhos: number }
  solicitacoes: { inicial: number; aceito: number; rejeitado: number; retirado: number; pendente: number }
  cobertura_auditavel: { valor: number | null; num: number; den: number }
  rodadas_ate_aprovacao: { media: number | null; casos: number }
  lacunas_resolvidas_por_rodada: { valor: number | null; lacunas: number; rodadas: number }
  baseline_roteirizado: { case_id: string; um_item_por_rodada: number; agrupado: number }[]
  espera_horas: { media: number | null; n: number }
  canal_util: Record<string, number>
  intervencoes: { total: number; por_motivo: Record<string, number>; abertas: number }
  retomadas: { total: number }
  modos: { ia: Record<string, number>; entrada_humana: number }
  efeito_indevido: { valor: number; nota: string }
}
export type EvalReport = { gate: string; result: string; reason?: string; date?: string; commit?: string; run_id?: string; scenarios?: { scenario: string; title: string; passed: boolean }[]; tests?: { exit_code: number } | null; metrics?: Record<string, number> } | null
