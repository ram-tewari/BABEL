import { Link } from "react-router";
import { Compass } from "lucide-react";
import { Empty } from "../components/ui";

export function NotFound() {
  return (
    <Empty icon={<Compass size={44} />} title="Nothing here">
      <Link to="/" className="text-accent underline-offset-4 hover:underline">
        Back to the library
      </Link>
    </Empty>
  );
}
