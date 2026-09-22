// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Language (FR-026) and audio retention (FR-027a). The language is stored on
 * the phone first, so it works offline, and synchronised when possible.
 */
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useI18n } from "../i18n";
import type { Language } from "../offline/db";

export function SettingsScreen({
  language,
  onLanguageChange,
}: {
  language: Language;
  onLanguageChange: (language: Language) => Promise<boolean>;
}) {
  const { t } = useI18n();
  const [retention, setRetention] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then((s) => setRetention(s.audio_retention_days), () => setRetention(null));
  }, []);

  const changeLanguage = async (next: Language) => {
    const synced = await onLanguageChange(next);
    setMessage(synced ? null : "ui.settings.offline");
  };

  return (
    <section className="stack">
      <h2>{t("ui.settings.language")}</h2>
      <div className="row">
        {(["fr", "en"] as const).map((option) => (
          <button
            key={option}
            type="button"
            className={option === language ? "primary" : ""}
            aria-pressed={option === language}
            onClick={() => void changeLanguage(option)}
          >
            {t(`language.${option}`)}
          </button>
        ))}
      </div>
      {retention !== null && (
        <label className="stack">
          {t("ui.settings.retention_days")}
          <input
            type="number"
            min={1}
            max={3650}
            value={retention}
            onChange={(event) => setRetention(Number(event.target.value))}
            onBlur={() =>
              void api
                .updateSettings({ audio_retention_days: retention })
                .then(() => setMessage("ui.settings.saved"))
            }
          />
          <small>{t("ui.settings.retention_help")}</small>
        </label>
      )}
      {message && <p className="notice" role="status">{t(message)}</p>}
    </section>
  );
}
