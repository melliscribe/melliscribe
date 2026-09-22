// Copyright (C) 2026 Jean-Christophe Giret
// SPDX-License-Identifier: AGPL-3.0-or-later
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { openCaptureDb } from "./offline/db";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) throw new Error("missing #root");

openCaptureDb().then((db) => {
  createRoot(root).render(
    <StrictMode>
      <App db={db} />
    </StrictMode>,
  );
});
