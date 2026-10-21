import { useEffect, useRef, useState } from "react";
import {
  Outlet,
  useLocation,
  useMatch,
  useOutletContext,
  useParams,
} from "react-router";
import useCourse from "../hooks/useCourse";
import usePersistentChat from "../hooks/usePersistentChat";
import ChatPanel from "../components/ChatPanel";

function CourseLayout() {
  const { courseId } = useParams();
  const { fileUpload, isChatOpen, setIsChatOpen } = useOutletContext();
  const location = useLocation();
  const isMapView = useMatch("/courses/:courseId") !== null;
  const [courseVersion, setCourseVersion] = useState(0);
  const { course, error } = useCourse(
    courseId,
    `${isMapView ? location.key : "topic"}:${courseVersion}`,
  );
  const topicMatch = useMatch("/courses/:courseId/topics/:topicId/*");
  const topicId = topicMatch?.params.topicId ?? null;
  const chatPath = topicId
    ? `/topics/${topicId}/messages`
    : `/courses/${courseId}/messages`;
  const persistentChat = usePersistentChat(chatPath, fileUpload, {
    onCourseChanged: () => setCourseVersion((version) => version + 1),
  });
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
        chat={persistentChat}
        title={topicId ? "Lesson chat" : "Course chat"}
        fileUpload={fileUpload}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen((prev) => !prev)}
      />
    </>
  );
}

export default CourseLayout;
