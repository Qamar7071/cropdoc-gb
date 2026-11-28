/* AI Agriculture Assistant: farmers ask in Urdu, Roman Urdu or English; answers are grounded in the
   CropDoc knowledge base (or show verified passages directly when the AI service is not configured). */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, BookOpen, Database, ExternalLink, Info, Leaf, Lightbulb, Send, Sparkles, User } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { PageShell } from "../components/PageShell";
import { Card, Disclaimer, ErrorBanner } from "../components/ui";
import { useI18n } from "../i18n";
import { api, type AssistantReply, type ChatTurn } from "../lib/api";

const URDU = /[؀-ۿ]/;
const SUGGESTIONS = [
  "میری فصل کے پتے پیلے کیوں ہو رہے ہیں؟",
  "گندم کی فصل کو بیماری سے کیسے بچاؤں؟",
  "What is the best way to protect tomato plants?",
  "How can I improve my crop yield?",
  "Which fertilizer is suitable for my crop?",
];

interface Turn extends ChatTurn {
  reply?: AssistantReply;
}

function relatedLink(item: AssistantReply["related"][number]): string {
  if (item.kind === "disease") return `/library/${encodeURIComponent(item.id)}`;
  if (item.kind === "crop") return `/crops/${encodeURIComponent(item.id)}`;
  return "/tips";
}

export function AssistantPage() {
  const { t, lang } = useI18n();
  const [params] = useSearchParams();
  const classId = params.get("class_id") ?? undefined;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState(params.get("q") ?? "");
  const end = useRef<HTMLDivElement>(null);
  const status = useQuery({ queryKey: ["assistant-status"], queryFn: api.assistantStatus, staleTime: 60_000 });
  const context = useQuery({ queryKey: ["disease", classId], queryFn: () => api.disease(classId!), enabled: !!classId });

  const chat = useMutation({
    mutationFn: (history: ChatTurn[]) => api.assistantChat(history.slice(-12), classId),
    onSuccess: (reply) => setTurns((current) => [...current, { role: "assistant", content: reply.reply, reply }]),
  });

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, chat.isPending]);

  function ask(text: string) {
    const question = text.trim();
    if (!question || chat.isPending) return;
    const history = [...turns.map(({ role, content }) => ({ role, content })), { role: "user" as const, content: question.slice(0, 2000) }];
    setTurns((current) => [...current, { role: "user", content: question }]);
    setDraft("");
    chat.mutate(history);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    ask(draft);
  }

  const ai = status.data?.ai_available;
  return (
    <PageShell title={t("assistant.title")} lead={t("assistant.lead")}>
      <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <Card className="flex min-h-[60dvh] flex-col !p-0" data-testid="assistant">
          <div className="flex flex-wrap items-center gap-2 border-b border-gray-100 px-4 py-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-700 text-white" aria-hidden="true">
              <Bot className="h-5 w-5" />
            </span>
            <p className="flex-1 font-bold text-gray-900">{t("assistant.name")}</p>
            {status.data && (
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${ai ? "bg-brand-100 text-brand-800" : "bg-gray-100 text-gray-700"}`}
                data-testid="assistant-mode"
              >
                {ai ? <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> : <Database className="h-3.5 w-3.5" aria-hidden="true" />}
                {ai ? t("assistant.modeAi") : t("assistant.modeKb")}
              </span>
            )}
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
            {context.data?.report && (
              <p className="flex items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-900" data-testid="assistant-context">
                <Leaf className="h-4 w-4 shrink-0" aria-hidden="true" />
                {t("assistant.context")}: <strong>{context.data.report.name.en}</strong>
                <span lang="ur" dir="rtl" className="urdu">({context.data.report.name.ur})</span>
              </p>
            )}
            {turns.length === 0 && (
              <div className="rounded-2xl border-2 border-dashed border-brand-200 bg-brand-50/50 p-5">
                <p className="flex items-center gap-2 font-bold text-gray-900">
                  <Lightbulb className="h-5 w-5 text-amber-500" aria-hidden="true" />
                  {t("assistant.try")}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => ask(q)}
                      lang={URDU.test(q) ? "ur" : "en"}
                      dir={URDU.test(q) ? "rtl" : "ltr"}
                      className={`rounded-full border border-brand-300 bg-white px-3 py-1.5 text-sm text-brand-900 hover:bg-brand-50 ${URDU.test(q) ? "urdu" : ""}`}
                      data-testid="assistant-suggestion"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((turn, index) => {
              const urdu = URDU.test(turn.content);
              const mine = turn.role === "user";
              return (
                <div key={index} className={`flex gap-2 ${mine ? "flex-row-reverse" : ""}`} data-testid={mine ? "chat-user" : "chat-assistant"}>
                  <span className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${mine ? "bg-gray-200 text-gray-700" : "bg-brand-700 text-white"}`} aria-hidden="true">
                    {mine ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </span>
                  <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${mine ? "bg-brand-700 text-white" : "bg-gray-50 text-gray-900"}`}>
                    <p lang={urdu ? "ur" : "en"} dir={urdu ? "rtl" : "ltr"} className={`whitespace-pre-line ${urdu ? "urdu text-right" : ""}`}>
                      {turn.content}
                    </p>
                    {turn.reply && (
                      <div className="mt-3 space-y-2 border-t border-gray-200 pt-2 text-xs text-gray-600">
                        {turn.reply.mode === "knowledge_base" && (
                          <p className="flex items-start gap-1" data-testid="assistant-kb-notice">
                            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            {turn.reply.notice === "ai_unavailable" ? t("assistant.aiDown") : t("assistant.aiOff")}
                          </p>
                        )}
                        {turn.reply.related.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {turn.reply.related.slice(0, 3).map((item) => (
                              <Link
                                key={`${item.kind}-${item.id}`}
                                to={relatedLink(item)}
                                className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 font-semibold text-brand-800 ring-1 ring-brand-200 hover:bg-brand-50"
                              >
                                <BookOpen className="h-3 w-3" aria-hidden="true" />
                                {(lang === "ur" || turn.reply?.language === "ur") && item.title.ur ? item.title.ur : item.title.en}
                              </Link>
                            ))}
                          </div>
                        )}
                        {turn.reply.sources.length > 0 && (
                          <details>
                            <summary className="cursor-pointer font-semibold">{t("assistant.sources")}</summary>
                            <ul className="mt-1 space-y-0.5">
                              {turn.reply.sources.map((url) => (
                                <li key={url}>
                                  <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 break-all underline latin">
                                    {url.replace(/^https?:\/\//, "").slice(0, 60)}
                                    <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                                  </a>
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {chat.isPending && (
              <p className="flex items-center gap-2 text-sm text-gray-600" data-testid="assistant-thinking">
                <Bot className="h-4 w-4 animate-pulse" aria-hidden="true" />
                {t("assistant.thinking")}
              </p>
            )}
            {chat.error != null && <ErrorBanner error={chat.error} />}
            <div ref={end} />
          </div>

          <form onSubmit={submit} className="flex items-end gap-2 border-t border-gray-100 p-3">
            <label className="sr-only" htmlFor="assistant-input">
              {t("assistant.placeholder")}
            </label>
            <textarea
              id="assistant-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  ask(draft);
                }
              }}
              rows={2}
              maxLength={2000}
              dir={URDU.test(draft) ? "rtl" : "auto"}
              placeholder={t("assistant.placeholder")}
              className={`min-h-[3rem] flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-base focus:border-brand-600 focus:outline-none ${URDU.test(draft) ? "urdu" : ""}`}
              data-testid="assistant-input"
            />
            <button
              type="submit"
              disabled={!draft.trim() || chat.isPending}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-700 text-white hover:bg-brand-800 disabled:bg-gray-300"
              aria-label={t("assistant.send")}
              data-testid="assistant-send"
            >
              <Send className="h-5 w-5 rtl:rotate-180" aria-hidden="true" />
            </button>
          </form>
        </Card>

        <aside className="space-y-4">
          <Card className="!p-4">
            <p className="text-sm font-bold text-gray-900">{t("assistant.howTitle")}</p>
            <ul className="mt-2 list-disc space-y-1 ps-5 text-sm text-gray-700">
              <li>{t("assistant.how1")}</li>
              <li>{t("assistant.how2")}</li>
              <li>{t("assistant.how3")}</li>
            </ul>
          </Card>
          {status.data && (
            <Card className="!p-4 text-xs text-gray-600" data-testid="assistant-privacy">
              <p>{status.data.privacy.en}</p>
              <p lang="ur" dir="rtl" className="urdu mt-1 text-right">{status.data.privacy.ur}</p>
            </Card>
          )}
          <Disclaimer />
        </aside>
      </div>
    </PageShell>
  );
}
