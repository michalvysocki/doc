import { Outlet, useOutletContext, useParams } from "react-router";
import useCourse from "../hooks/useCourse";
import ChatPanel from "../components/ChatPanel";

function CourseLayout() {
  const { courseId } = useParams();
  const { chat, fileUpload, isChatOpen, setIsChatOpen } = useOutletContext();
  const { course, error } = useCourse(courseId);

  return (
    <>
      <main className="flex-1 overflow-y-auto p-6">
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
