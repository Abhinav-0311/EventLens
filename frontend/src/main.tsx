import { createRoot } from "react-dom/client";
import App from "./App";
import { RenderBoundary } from "./ui";
import "./styles.css";
createRoot(document.getElementById("root")!).render(
  <RenderBoundary>
    <App />
  </RenderBoundary>,
);
