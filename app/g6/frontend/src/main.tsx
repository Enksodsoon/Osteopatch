import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyStoredPreference } from "./theme";
import "./styles.css";

// U005: paint the stored theme before React renders anything. With a stored
// explicit choice this is what keeps the first frame from flashing the system
// theme; it is deliberately the only pre-render work, and it cannot throw.
applyStoredPreference();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
