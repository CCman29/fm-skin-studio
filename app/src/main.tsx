import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { applyTheme, savedTheme } from "./theme";

applyTheme(savedTheme());
if (window.fmskin?.platform) document.documentElement.dataset.platform = window.fmskin.platform;

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
