import { useQuery } from "@tanstack/react-query";
import { BookOpen, Cpu, ShieldCheck, Scale } from "lucide-react";

import { PageShell } from "../components/PageShell";
import { Card, CardTitle, Disclaimer, IconBubble } from "../components/ui";
import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { KeyFacts } from "./HomePage";

export function AboutPage() {
  const { t } = useI18n();
  const model = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity });
  const card = model.data?.model_card;
  return (
    <PageShell title={t("about.title")} lead={t("about.what")}>
      <Card>
        <CardTitle icon={<IconBubble tone="soft"><Cpu className="h-6 w-6" /></IconBubble>} title={t("about.model")} />
        {model.data?.model_loaded ? (
          <>
            <p className="mb-3 text-gray-800">
              {String(card?.architecture ?? "")} · {t("about.version")}: <span className="latin font-semibold">{model.data.model_version}</span>
            </p>
            <KeyFacts />
            {Array.isArray(card?.limitations) && (
              <ul className="mt-4 list-disc space-y-1 ps-5 text-sm text-gray-700">
                {card.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p className="text-gray-700">{t("about.notLoaded")}</p>
        )}
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardTitle icon={<IconBubble tone="soft"><BookOpen className="h-6 w-6" /></IconBubble>} title={t("about.data")} />
          <p className="text-gray-800">{t("about.dataBody")}</p>
          <p className="mt-3 text-sm text-gray-700">{t("result.coverage")}</p>
        </Card>
        <Card>
          <CardTitle icon={<IconBubble tone="soft"><ShieldCheck className="h-6 w-6" /></IconBubble>} title={t("result.disclaimer").split(".")[0]} />
          <p className="font-semibold text-gray-900">{t("about.notReplacement")}</p>
          <p className="mt-3 text-gray-800">{t("about.privacy")}</p>
        </Card>
      </div>
      <Card>
        <CardTitle icon={<IconBubble tone="soft"><Scale className="h-6 w-6" /></IconBubble>} title={t("about.licenses")} />
        <p className="text-gray-800">{t("about.licensesBody")}</p>
      </Card>
      <Disclaimer />
    </PageShell>
  );
}

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <PageShell title={t("notFound.title")}>
      <Card>
        <a href="/" className="font-semibold text-brand-800 underline">
          {t("notFound.back")}
        </a>
      </Card>
    </PageShell>
  );
}
