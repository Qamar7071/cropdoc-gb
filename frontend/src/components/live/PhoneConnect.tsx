/* "Use it on your phone": QR code of the HTTPS address in phone mode, otherwise how to turn it on. */
import { useQuery } from "@tanstack/react-query";
import { Smartphone } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { useI18n } from "../../i18n";
import { api } from "../../lib/api";

export function PhoneConnect({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  const network = useQuery({ queryKey: ["network"], queryFn: api.network, staleTime: 60_000, retry: false });
  const url = network.data?.urls[0] ?? null;
  const [qr, setQr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    if (!url) return;
    QRCode.toDataURL(url, { margin: 1, width: 220, color: { dark: "#062716", light: "#ffffff" } })
      .then((data) => alive && setQr(data))
      .catch(() => alive && setQr(null));
    return () => {
      alive = false;
    };
  }, [url]);

  return (
    <section className={`rounded-2xl border border-brand-100 bg-white ${compact ? "p-4" : "p-5"} shadow-sm`} data-testid="phone-connect">
      <h3 className="flex items-center gap-2 text-base font-bold text-gray-900">
        <Smartphone className="h-5 w-5 text-brand-700" aria-hidden="true" />
        {t("phone.title")}
      </h3>
      {url ? (
        <div className="mt-3 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          {qr && <img src={qr} alt={t("phone.qrAlt")} width={150} height={150} className="rounded-lg border border-gray-200" data-testid="phone-qr" />}
          <div className="text-sm text-gray-700">
            <p>{t("phone.scan")}</p>
            {network.data?.urls.map((address) => (
              <p key={address} dir="ltr" className="latin mt-1 font-mono text-[13px] font-semibold break-all text-brand-800">
                {address}
              </p>
            ))}
            <p className="mt-2 text-xs text-gray-600">{t("phone.warning")}</p>
          </div>
        </div>
      ) : (
        <div className="mt-2 space-y-2 text-sm text-gray-700">
          <p>{t("phone.howTo")}</p>
          <p dir="ltr" className="latin rounded-lg bg-gray-900 px-3 py-2 font-mono text-[13px] text-emerald-300">start-phone.bat</p>
          <p className="text-xs text-gray-600">{t("phone.howToMac")}</p>
        </div>
      )}
    </section>
  );
}
