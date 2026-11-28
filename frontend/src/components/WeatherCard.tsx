/* Weather for the selected district (or the phone's location), with general farming notes. */
import { useQuery } from "@tanstack/react-query";
import { CloudOff, CloudRain, CloudSun, Droplet, LocateFixed, MapPin, Thermometer, Wind } from "lucide-react";
import { useState } from "react";

import { useI18n } from "../i18n";
import { api } from "../lib/api";
import { useDistrict } from "../state/district";
import { Card, Skeleton } from "./ui";

export function WeatherCard() {
  const { t, lang, district: districtName } = useI18n();
  const { district } = useDistrict();
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const place = coords ? undefined : district || "Gilgit";
  const weather = useQuery({
    queryKey: ["weather", place ?? `${coords?.lat},${coords?.lon}`],
    queryFn: () => api.weather(coords ? { lat: coords.lat, lon: coords.lon } : { district: place }),
    staleTime: 15 * 60_000,
    retry: false,
  });

  function useMyLocation() {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        // rounded on the server too; only ~10 km precision is ever used
        setCoords({ lat: Math.round(position.coords.latitude * 10) / 10, lon: Math.round(position.coords.longitude * 10) / 10 });
        setLocating(false);
      },
      () => setLocating(false),
      { timeout: 10_000, maximumAge: 30 * 60_000 },
    );
  }

  const w = weather.data;
  const pick = (text?: { en: string; ur: string }) => (text ? (lang === "ur" ? text.ur : text.en) : "");
  return (
    <Card className="!p-5" data-testid="weather-card">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <CloudSun className="h-6 w-6 text-brand-700" aria-hidden="true" />
        <h2 className="flex-1 text-lg font-bold text-gray-900">{t("weather.title")}</h2>
        <button
          type="button"
          onClick={useMyLocation}
          disabled={locating}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <LocateFixed className="h-3.5 w-3.5" aria-hidden="true" />
          {locating ? t("weather.locating") : t("weather.myLocation")}
        </button>
      </div>
      {weather.isPending && <Skeleton className="h-32 w-full" />}
      {w && !w.available && (
        <p className="flex items-start gap-2 rounded-xl bg-gray-50 p-3 text-sm text-gray-700" data-testid="weather-unavailable">
          <CloudOff className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {w.reason === "disabled" ? t("weather.disabled") : t("weather.unavailable")}
        </p>
      )}
      {weather.isError && (
        <p className="flex items-start gap-2 rounded-xl bg-gray-50 p-3 text-sm text-gray-700">
          <CloudOff className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {t("weather.unavailable")}
        </p>
      )}
      {w?.available && w.current && (
        <div className="space-y-3">
          <p className="flex items-center gap-1 text-sm text-gray-600">
            <MapPin className="h-4 w-4" aria-hidden="true" />
            {w.place ? districtName(w.place) : t("weather.nearYou")}
          </p>
          <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
            <p className="text-4xl font-bold text-gray-900">
              <span dir="ltr" className="latin">{w.current.temperature != null ? Math.round(w.current.temperature) : "–"}°C</span>
            </p>
            <p className="text-lg font-semibold text-gray-800">{pick(w.current.summary)}</p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-gray-700">
            <span className="flex items-center gap-1">
              <Droplet className="h-4 w-4" aria-hidden="true" />
              {t("weather.humidity")}: <span dir="ltr" className="latin">{w.current.humidity ?? "–"}%</span>
            </span>
            <span className="flex items-center gap-1">
              <Wind className="h-4 w-4" aria-hidden="true" />
              <span dir="ltr" className="latin">{w.current.wind_kmh ?? "–"} km/h</span>
            </span>
          </div>
          <ul className="grid grid-cols-3 gap-2" data-testid="weather-days">
            {(w.daily ?? []).map((day) => (
              <li key={day.date} className="rounded-xl bg-brand-50 p-2 text-center text-xs">
                <p className="font-semibold">{new Date(day.date).toLocaleDateString(lang === "ur" ? "ur-PK" : "en-GB", { weekday: "short" })}</p>
                <p className="mt-0.5 text-gray-700">{pick(day.summary)}</p>
                <p className="mt-0.5 flex items-center justify-center gap-1 font-semibold">
                  <Thermometer className="h-3 w-3" aria-hidden="true" />
                  <span dir="ltr" className="latin">{day.temp_min != null ? Math.round(day.temp_min) : "–"}–{day.temp_max != null ? Math.round(day.temp_max) : "–"}°</span>
                </p>
                <p className="flex items-center justify-center gap-1 text-gray-600">
                  <CloudRain className="h-3 w-3" aria-hidden="true" />
                  <span dir="ltr" className="latin">{day.precipitation_probability ?? "–"}%</span>
                </p>
              </li>
            ))}
          </ul>
          <ul className="space-y-1 rounded-xl bg-amber-50 p-3 text-sm text-amber-950" data-testid="weather-advice">
            {(w.advisories ?? []).map((note) => (
              <li key={note.en}>• {pick(note)}</li>
            ))}
          </ul>
          <p className="text-[11px] text-gray-500">
            {pick(w.advisory_note)} {w.attribution}
          </p>
        </div>
      )}
    </Card>
  );
}
