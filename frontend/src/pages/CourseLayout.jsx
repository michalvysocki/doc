import { useEffect, useRef } from "react";
import {
  Outlet,
  useLocation,
  useMatch,
  useOutletContext,
  useParams,
} from "react-router";
import useCourse from "../hooks/useCourse";
import ChatPanel from "../components/ChatPanel";

function CourseLayout() {
  const { courseId } = useParams();
  const { chat, fileUpload, isChatOpen, setIsChatOpen } = useOutletContext();
  const location = useLocation();
  const isMapView = useMatch("/courses/:courseId") !== null;
  const { course, error } = useCourse(
    courseId,
    isMapView ? location.key : "topic",
  );
  const mainRef = useRef(null);

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <>
      <main ref={mainRef} className="flex-1 overflow-y-auto p-6">
        {error ? (
          <p className="text-sm text-warn">{error}</p>
        ) : course === null ? (
          <p className="text-sm text-ink/60">Loading course...</p>
        ) : (
          <Outlet context={{ course }} />
        )}
      </main>

      <ChatPanel
        chat={chat}
        fileUpload={fileUpload}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen((prev) => !prev)}
      />
    </>
  );
}

export default CourseLayout;
