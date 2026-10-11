import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

// Demo tool to verify the Slack approval (HITL) flow end-to-end.
// Gated on always() so EVERY call pauses for a human Approve/Cancel.
// Safe: no side effects, returns canned data only.
export default defineTool({
  description:
    "Demo approval-gated action. Call this when the user asks to test approvals. Returns a canned confirmation.",
  inputSchema: z.object({
    action: z.string().min(1).describe("Label for the demo action, e.g. 'publish report'"),
  }),
  approval: always(),
  async execute({ action }) {
    return {
      approved_action: action,
      result: "executed after human approval",
      sample: true,
    };
  },
});
