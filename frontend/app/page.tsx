import { Suspense } from "react";
import { StartView } from "@/components/StartView";

export default function Home() {
  return (
    <Suspense>
      <StartView />
    </Suspense>
  );
}
