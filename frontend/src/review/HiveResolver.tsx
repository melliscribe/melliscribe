// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Resolve a flagged hive (FR-015b): pick an existing hive, or create one from
 * the identifier that was said. Creating is an explicit tap — the system never
 * creates a hive on its own (FR-015c).
 */
import { useEffect, useState } from "react";

import { api, type Hive } from "../api/client";
import { useI18n } from "../i18n";

export function HiveResolver({
  spokenIdentifier,
  onResolve,
}: {
  spokenIdentifier: string | null | undefined;
  onResolve: (choice: { hive_id: string } | { identifier: string }) => void;
}) {
  const { t } = useI18n();
  const [hives, setHives] = useState<Hive[]>([]);
  const [name, setName] = useState(spokenIdentifier ?? "");
  useEffect(() => {
    api.listHives().then(setHives, () => setHives([]));
  }, []);
  return (
    <div className="stack">
      <strong>{t("ui.review.hive_unresolved")}</strong>
      <div className="choices">
        {hives.map((hive) => (
          <button key={hive.id} type="button" onClick={() => onResolve({ hive_id: hive.id })}>
            {hive.identifier}
          </button>
        ))}
      </div>
      <label className="stack">
        {t("ui.review.hive_new_name")}
        <input value={name} onChange={(event) => setName(event.target.value)} />
      </label>
      <button
        type="button"
        className="primary"
        disabled={!name.trim()}
        onClick={() => onResolve({ identifier: name.trim() })}
      >
        {t("ui.review.hive_create", { identifier: name.trim() })}
      </button>
    </div>
  );
}
