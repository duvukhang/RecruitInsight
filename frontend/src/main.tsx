import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { BrowserRouter } from "react-router-dom";
import "./tailwind.css";
import "./style.css";
import "./workspace.css";
const client = new QueryClient({ defaultOptions: { queries: { retry: 1 } } });
createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </BrowserRouter>,
);
