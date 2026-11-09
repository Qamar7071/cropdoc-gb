/* "Was this correct?" Yes/No; on No, the farmer picks the right class. Stored for future few-shot adaptation. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { useI18n } from "../../i18n";
import { api, type Feedback } from "../../lib/api";
import { Button } from "../ui";

export function FeedbackControl({ scanId, existing }: { scanId: string | null; existing?: Feedback | null }) {
  const { t, crop } = useI18n();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"ask" | "pick" | "done">(existing ? "done" : "ask");
  const [choice, setChoice] = useState("");
  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  const mutation = useMutation({
    mutationFn: (body: { correct: boolean; correct_class_id?: string }) => api.feedback(scanId as string, body),
    onSuccess: () => {
      setMode("done");
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  if (!scanId) {
    return <p className="text-sm text-gray-600">{t("feedback.saveFirst")}</p>;
  }
  if (mode === "done") {
    return (
      <p className="flex items-center gap-2 text-sm font-semibold text-brand-800" role="status">
        <Check className="h-4 w-4" aria-hidden="true" />
        {t("feedback.thanks")}
      </p>
    );
  }
  const classes = model.data?.classes ?? [];
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-3" data-testid="feedback">
      <p className="mb-2 text-sm font-bold text-gray-900">{t("feedback.question")}</p>
      {mode === "ask" ? (
        <div className="flex gap-2">
          <Button variant="secondary" className="px-4 py-1.5" onClick={() => mutation.mutate({ correct: true })} disabled={mutation.isPending}>
            <ThumbsUp className="h-4 w-4" aria-hidden="true" />
            {t("feedback.yes")}
          </Button>
          <Button variant="secondary" className="px-4 py-1.5" onClick={() => setMode("pick")}>
            <ThumbsDown className="h-4 w-4" aria-hidden="true" />
            {t("feedback.no")}
          </Button>
        </div>
      ) : (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            if (choice) mutation.mutate({ correct: false, correct_class_id: choice });
          }}
        >
          <label className="flex-1">
            <span className="sr-only">{t("feedback.pick")}</span>
            <select
              value={choice}
              onChange={(event) => setChoice(event.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
              required
            >
              <option value="">{t("feedback.pick")}</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {crop(c.crop)}: {c.disease}
                </option>
              ))}
            </select>
          </label>
          <Button type="submit" className="px-4 py-2" disabled={!choice || mutation.isPending}>
            {t("feedback.submit")}
          </Button>
        </form>
      )}
    </div>
  );
}
