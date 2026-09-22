// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useState } from "react";

import { api, uploadRecording } from "./api/client";
import { CaptureScreen } from "./capture/CaptureScreen";
import { I18nProvider, translate } from "./i18n";
import type { CaptureDb, Language } from "./offline/db";
import { requestPersistence } from "./offline/quota";
import { UploadQueue } from "./offline/queue";
import { loadLanguage, storeLanguage } from "./offline/settings";
import { PendingList } from "./review/PendingList";
import { RecordList } from "./review/RecordList";
import { RecordReview } from "./review/RecordReview";
import { SettingsScreen } from "./review/SettingsScreen";

type Tab = "capture" | "review" | "pending" | "settings";

export function App({ db }: { db: CaptureDb }) {
  const [language, setLanguage] = useState<Language | null>(null);
  const [tab, setTab] = useState<Tab>("capture");
  const [openRecord, setOpenRecord] = useState<string | null>(null);
  const queue = useMemo(() => new UploadQueue(db, uploadRecording), [db]);

  useEffect(() => {
    void requestPersistence();
    const stop = queue.start();
    void (async () => {
      setLanguage(await loadLanguage(db));
      try {
        const server = await api.getSettings();
        await storeLanguage(db, server.language);
        setLanguage(server.language);
      } catch {
        // Offline: the phone's copy is authoritative until the server is reachable.
      }
    })();
    return stop;
  }, [db, queue]);

  if (language === null) return null;

  const changeLanguage = async (next: Language) => {
    await storeLanguage(db, next);
    setLanguage(next);
    try {
      await api.updateSettings({ language: next });
      return true;
    } catch {
      return false;
    }
  };

  const tabs: Tab[] = ["capture", "review", "pending", "settings"];
  return (
    <I18nProvider language={language}>
      <main lang={language}>
        {tab === "capture" && <CaptureScreen db={db} queue={queue} language={language} />}
        {tab === "review" &&
          (openRecord ? (
            <RecordReview recordId={openRecord} onBack={() => setOpenRecord(null)} />
          ) : (
            <RecordList onOpen={setOpenRecord} />
          ))}
        {tab === "pending" && <PendingList db={db} />}
        {tab === "settings" && <SettingsScreen language={language} onLanguageChange={changeLanguage} />}
      </main>
      <nav className="tabs">
        {tabs.map((name) => (
          <button
            key={name}
            type="button"
            aria-current={tab === name ? "page" : undefined}
            onClick={() => {
              setTab(name);
              setOpenRecord(null);
            }}
          >
            {translate(language, `ui.nav.${name}`)}
          </button>
        ))}
      </nav>
    </I18nProvider>
  );
}
