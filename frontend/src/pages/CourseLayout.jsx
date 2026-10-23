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
import Skeleton from "../components/Skeleton";
import EmptyState from "../components/EmptyState";
import { CircleAlert } from "lucide-react";

function CourseLayout() {
  const { courseId } = useParams();
  const { fileUpload, isChatOpen, setIsChatOpen, refreshCourses } =
    useOutletContext();
  const location = useLocation();
  const isMapView = useMatch("/courses/:courseId") !== null;
  const [courseVersion, setCourseVersion] = useState(0);
  const refreshCourse = () => {
    setCourseVersion((version) => version + 1);
    refreshCourses();
  };
  const { course, error } = useCourse(
    courseId,
    `${isMapView ? location.key : "topic"}:${courseVersion}`,
  );
  const topicMatch = useMatch("/courses/:courseId/topics/:topicId/*");
  const topicId = topicMatch?.params.topicId ?? null;
  const coursePath = `/courses/${courseId}/messages`;
  const chatPath = topicId ? `/topics/${topicId}/messages` : coursePath;
  const persistentChat = usePersistentChat(chatPath, fileUpload, {
    onCourseChanged: refreshCourse,
  });
  const topicDeletions = useTopicDeletions(courseId, courseVersion, {
    onResolved: (note, action) => {
      persistentChat.appendMessage(coursePath, note);
      if (action === "confirm") refreshCourse();
    },
  });
  const courseRebuild = useCourseRebuild(courseId, courseVersion, {
    onResolved: (note, action) => {
      persistentChat.appendMessage(coursePath, note);
      if (action === "apply") refreshCourse();
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
      if (action === "confirm") refreshCourse();
    },
  });
  const mainRef = useRef(null);

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <>
      <main ref={mainRef} className="flex-1 overflow-y-auto p-4 sm:p-6">
        {error ? (
          <EmptyState
            icon={CircleAlert}
            title="Couldn't load the course"
            text={error}
            action={
              <button
                type="button"
                onClick={() => setCourseVersion((version) => version + 1)}
                className="btn-secondary"
              >
                Try again
              </button>
            }
          />
        ) : course === null ? (
          <div className="max-w-3xl mx-auto w-full">
            <Skeleton lines={1} className="w-1/2" />
            <Skeleton lines={6} className="mt-8" />
          </div>
        ) : (
          <Outlet
            context={{ course, courseVersion, courseRebuild, refreshCourse }}
          />
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
        emptyState={
          topicId
            ? {
                title: "Ask about this lesson",
                text: "…or ask to regenerate it, add tasks or subtopics.",
              }
            : {
                title: "Ask about the course",
                text: "…or ask to add, move or delete topics, or rebuild the course.",
              }
        }
        placeholder={
          topicId ? "Ask about the lesson..." : "Ask about the course..."
        }
      />
    </>
  );
}

export default CourseLayout;
