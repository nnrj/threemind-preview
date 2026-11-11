// Isolated preview/export harness. This entry is not part of the production build.
import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import LanguageReplayPage from "../../src/v2/replay/LanguageReplayPage";
import LanguageReplayPlayer from "../../src/v2/replay/LanguageReplayPlayer";
import { LanguageReplayRenderer, parseLanguageReplay, heldSample } from "../../src/v2/replay/languageReplay";
import { Workspace } from "../../src/v2/ui";
import "../../src/v2/style.css";

const root = createRoot(document.getElementById("root")!);
let renderer: LanguageReplayRenderer | undefined;
Object.assign(window, { languageReplayHarness: {
  load(value: unknown) { const data = parseLanguageReplay(value); renderer = new LanguageReplayRenderer(data); root.render(<main style={{padding:16,maxWidth:1600,margin:"0 auto"}}><LanguageReplayPlayer key={data.title} data={data}/></main>); return renderer.duration; },
  page(projectId: string) { root.render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Workspace.Provider value={{ project: {id:projectId,name:"Replay fixture",role:"owner",created_at:""},projects:[],user:null }}><main style={{padding:16}}><LanguageReplayPage/></main></Workspace.Provider></MemoryRouter></QueryClientProvider>); },
  frame(seconds: number) { if(!renderer) throw new Error("Replay not loaded"); return renderer.render(seconds).toDataURL("image/png").split(",")[1]; },
  validate: parseLanguageReplay, heldSample,
}});
