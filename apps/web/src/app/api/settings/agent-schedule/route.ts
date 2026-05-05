import { z } from "zod";
import { jsonError, jsonOk } from "@/lib/api/http";
import {
  loadOrInitScheduleSettings,
  updateScheduleSettings,
  type ScheduleSettingsUpdate,
} from "@/lib/scheduler/scheduleSettings";
import { requireDefaultUser } from "@/lib/server/defaultUser";

const updateSchema = z.object({
  enabled: z.boolean().optional(),
  schedulePreset: z
    .enum([
      "every_15_min",
      "every_30_min",
      "hourly",
      "every_2h",
      "every_4h",
      "daily_after_close",
      "daily_before_open",
      "custom",
    ])
    .optional(),
  frequencyMinutes: z.number().int().min(1).max(60 * 24 * 7).optional(),
  customCronExpression: z.union([z.string().min(1).max(120), z.null()]).optional(),
  timezone: z.string().min(1).max(64).optional(),
  runOnlyDuringMarketHours: z.boolean().optional(),
  runOnMarketDaysOnly: z.boolean().optional(),
  skipIfRunAlreadyActive: z.boolean().optional(),
  maxRunDurationMinutes: z.number().int().min(1).max(180).optional(),
  retryFailedRuns: z.boolean().optional(),
  maxRetries: z.number().int().min(0).max(10).optional(),
});

export async function GET() {
  try {
    const user = await requireDefaultUser();
    const s = await loadOrInitScheduleSettings(user.id);
    return jsonOk(s);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}

export async function PUT(req: Request) {
  try {
    const user = await requireDefaultUser();
    const raw = await req.json().catch(() => null);
    const parsed = updateSchema.safeParse(raw);
    if (!parsed.success) {
      return jsonError(parsed.error.flatten().formErrors.join("; ") || "Invalid body", 400);
    }
    const updated = await updateScheduleSettings(user.id, parsed.data as ScheduleSettingsUpdate);
    return jsonOk(updated);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
