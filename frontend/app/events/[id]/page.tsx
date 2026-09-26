import { Suspense } from "react";
import { EventDetailView } from "@/components/EventDetailView";

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <EventDetailView eventId={id} />
    </Suspense>
  );
}
