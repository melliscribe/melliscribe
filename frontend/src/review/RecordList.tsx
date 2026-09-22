// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";

import { api, type Hive, type RecordView } from "../api/client";
import { useI18n } from "../i18n";

function countOpenFlags(record: RecordView): number {
  const fields = [
    record.hive,
    record.inspection_date,
    record.queen_seen,
    record.brood,
    record.stores,
    record.temperament,
    record.brood_pattern,
    record.brood_frames,
    record.stores_frames,
    record.bee_frames,
    ...(record.treatments ?? []).flatMap((t) => [t.product, t.dose]),
    ...(record.actions_to_do ?? []).map((a) => a.text),
  ];
  return (
    fields.filter((f) => f.status === "uncertain").length + (record.hive.value == null ? 1 : 0)
  );
}

export function RecordList({ onOpen }: { onOpen: (id: string) => void }) {
  const { t, formatDate } = useI18n();
  const [records, setRecords] = useState<RecordView[] | null>(null);
  const [hives, setHives] = useState<Record<string, string>>({});
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    Promise.all([api.listRecords(), api.listHives()]).then(
      ([loaded, loadedHives]: [RecordView[], Hive[]]) => {
        setRecords(loaded);
        setHives(Object.fromEntries(loadedHives.map((h) => [h.id, h.identifier])));
      },
      () => setOffline(true),
    );
  }, []);

  if (offline) return <p className="notice warn">{t("ui.error.network")}</p>;
  if (records === null) return <p>…</p>;
  if (records.length === 0) return <p>{t("ui.review.empty")}</p>;
  return (
    <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
      {records.map((record) => {
        const flags = countOpenFlags(record);
        const date = record.inspection_date.value ?? record.captured_on;
        const hive = record.hive.value ? hives[record.hive.value] : record.spoken_hive_identifier;
        return (
          <li key={record.id} className={`field list-item ${flags ? "flagged" : ""}`}>
            <div>
              <strong>{hive ?? t("ui.review.hive_unresolved")}</strong> — {formatDate(date)}
              <div>
                {record.confirmed_at != null
                  ? t("ui.review.confirmed")
                  : flags
                    ? t("ui.review.open_flags", { count: flags })
                    : t("ui.review.unconfirmed")}
              </div>
            </div>
            <button type="button" onClick={() => onOpen(record.id)}>
              {t("ui.review.open")}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
