import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";
import "./index.css";
import "./lib/prefs";
import { Library } from "./pages/Library";
import { NovelPage } from "./pages/Novel";
import { Reader } from "./pages/Reader";
import { NotFound } from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/novel/:id" element={<NovelPage />} />
          <Route path="/novel/:id/:tab" element={<NovelPage />} />
          <Route path="/read/:chapterId" element={<Reader />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
