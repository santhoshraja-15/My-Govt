/** Plain-language account of how far routing got (never implies an office exists when it does not). */
export function assignmentText(state: string, department?: string | null, authority?: string | null): string {
  switch (state) {
    case "authority_assigned": return `Assigned to ${authority ?? "the responsible authority"}${department ? ` (${department})` : ""}.`;
    case "department_level":   return `Routed to ${department ?? "the department"} at department level. A specific office or officer has not been assigned yet.`;
    case "department_only":    return `Department identified: ${department ?? "—"}. No handling authority is configured for it yet, so it will be assigned manually.`;
    default:                   return "Not yet routed to a department. It is awaiting triage.";
  }
}

import type { TKey, Vars } from "@/lib/i18n";

/** Same wording as assignmentText(), translated through the locale dictionaries. */
export function assignmentTextT(t: (k: TKey, v?: Vars) => string, state: string, department?: string | null, authority?: string | null): string {
  switch (state) {
    case "authority_assigned":
      if (!authority) return t("cmp.asg.authorityDefault");
      return department ? t("cmp.asg.authority", { authority, department }) : t("cmp.asg.authorityNoDept", { authority });
    case "department_level": return t("cmp.asg.department_level", { department: department ?? t("cmp.thisDepartment") });
    case "department_only": return t("cmp.asg.department_only", { department: department ?? "—" });
    default: return t("cmp.asg.pending");
  }
}
