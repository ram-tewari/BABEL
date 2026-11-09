import { useParams } from "react-router";
import { Player } from "../vn/Player";

/** /vn/:chapterId — the curtains open straight onto a chapter. */
export function VisualNovel() {
  const { chapterId } = useParams();
  return <Player key={chapterId} chapterId={Number(chapterId)} />;
}

/** /play/:novelId — the title screen: Begin / Continue. */
export function PlayNovel() {
  const { novelId } = useParams();
  return <Player key={`t${novelId}`} novelId={Number(novelId)} title />;
}
