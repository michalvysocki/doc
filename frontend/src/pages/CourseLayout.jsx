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
import useTopicDeletions from "../hooks/useTopicDeletions";
import useCourseRebuild from "../hooks/useCourseRebuild";
import useRegenerations from "../hooks/useRegenerations";
import useCourseFiles from "../hooks/useCourseFiles";
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
  const coursePath = `/courses/${courseId}/messages`;
  const chatPath = topicId ? `/topics/${topicId}/messages` : coursePath;
  const persistentChat = usePersistentChat(chatPath, fileUpload, {
    onCourseChanged: () => setCourseVersion((version) => version + 1),
  });
  const topicDeletions = useTopicDeletions(courseId, courseVersion, {
    onResolved: (note, action) => {
      persistentChat.appendMessage(coursePath, note);
      if (action === "confirm") setCourseVersion((version) => version + 1);
    },
  });
  const courseRebuild = useCourseRebuild(courseId, courseVersion, {
    onResolved: (note, action) => {
      persistentChat.appendMessage(coursePath, note);
      if (action === "apply") setCourseVersion((version) => version + 1);
    },
  });
  const courseFiles = useCourseFiles(courseId, {
    onRemoved: (file) =>
      fileUpload.setDocuments((prev) =>
        prev.filter((doc) => doc.file_uuid !== file.id),
      ),
  });
  const regenerations = useRegenerations(topicId, courseVersion, {
    onResolved: (note, proposal, action) => {
      persistentChat.appendMessage(
        `/topics/${proposal.topic_id}/messages`,
        note,
      );
      if (action === "confirm") setCourseVersion((version) => version + 1);
    },
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
          <Outlet context={{ course, courseVersion, courseRebuild }} />
        )}
      </main>

      <ChatPanel
        chat={persistentChat}
        title={topicId ? "Lesson chat" : "Course chat"}
        fileUpload={fileUpload}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen((prev) => !prev)}
        topicDeletions={topicId ? null : topicDeletions}
        regenerations={topicId ? regenerations : null}
        courseFiles={courseFiles}
        placeholder={
          topicId
            ? "Ask about the lesson, or ask to regenerate it, add tasks or subtopics..."
            : "Ask about the course, or ask to add, rename, move, delete topics or rebuild it..."
        }
      />
    </>
  );
}

export default CourseLayout;
