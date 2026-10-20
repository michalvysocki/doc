import { useState } from "react";
import useFileUpload from "./hooks/useFileUpload";
import useChat from "./hooks/useChat";
import useCourse from "./hooks/useCourse";
import useCourses from "./hooks/useCourses";
import ChatPanel from "./components/ChatPanel";
import CoursePrompt from "./components/CoursePrompt";
import CourseView from "./components/CourseView";
import Sidebar from "./components/Sidebar";

function App() {
  const fileUpload = useFileUpload();
  const chat = useChat(fileUpload);
  const courseState = useCourse();
  const coursesState = useCourses();
  const [isChatOpen, setIsChatOpen] = useState(true);

  async function handleCreateCourse(initialPrompt) {
    const created = await courseState.createCourse(initialPrompt);
    if (created) coursesState.addCourse(created);
  }

  async function handleDeleteCourse(course) {
    const confirmed = window.confirm(
      `Delete course "${course.title}"? This cannot be undone.`,
    );
    if (!confirmed) return;

    const deleted = await coursesState.removeCourse(course.id);
    if (deleted && courseState.course?.id === course.id) {
      courseState.startNewCourse();
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar
        courses={coursesState.courses}
        activeCourseId={courseState.course?.id ?? null}
        onSelectCourse={courseState.loadCourse}
        onNewCourse={courseState.startNewCourse}
        onDeleteCourse={handleDeleteCourse}
        isLoading={coursesState.isLoading}
        error={coursesState.error}
        disabled={courseState.isCreating}
      />

      {courseState.course === null ? (
        <div className="flex-1 flex items-center justify-center px-4">
          {courseState.isLoading ? (
            <p className="text-sm text-ink/60">Loading course...</p>
          ) : (
            <CoursePrompt
              onSubmit={handleCreateCourse}
              isLoading={courseState.isCreating}
              error={courseState.error}
            />
          )}
        </div>
      ) : (
        <>
          <main className="flex-1 overflow-y-auto p-6">
            <CourseView course={courseState.course} />
          </main>

          <ChatPanel
            chat={chat}
            fileUpload={fileUpload}
            isOpen={isChatOpen}
            onToggle={() => setIsChatOpen((prev) => !prev)}
          />
        </>
      )}
    </div>
  );
}

export default App;
