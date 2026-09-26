import { Suspense } from "react";
import { EventListView } from "@/components/EventListView";

export default function EventsPage() {
  return (
    <Suspense>
      <EventListView />
    </Suspense>
  );
}
