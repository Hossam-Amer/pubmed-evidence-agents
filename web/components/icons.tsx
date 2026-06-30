import {
  Activity,
  BarChart3,
  Binary,
  CircleDot,
  Database,
  Image as ImageIcon,
  PenLine,
  Puzzle,
  RefreshCw,
  Satellite,
  Scale,
  Scissors,
  Search,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

const STEP_ICONS: Record<string, LucideIcon> = {
  Pipeline: Activity,
  Vision: ImageIcon,
  PICO: Puzzle,
  Cache: Database,
  PubMed: Satellite,
  Preprocess: Scissors,
  Embed: Binary,
  FAISS: Search,
  TopK: BarChart3,
  Consensus: Scale,
  Generator: PenLine,
  Verifier: ShieldCheck,
  LoopCtrl: RefreshCw,
};

export function stepIcon(step: string): LucideIcon {
  return STEP_ICONS[step] ?? CircleDot;
}
