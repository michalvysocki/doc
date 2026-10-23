import { useState } from "react";
import { Outlet, useMatch, useNavigate } from "react-router";
import useFileUpload from "../hooks/useFileUpload";
import useCourses from "../hooks/useCourses";
import useCreateCourse from "../hooks/useCreateCourse";
import Sidebar from "../components/Sidebar";
import { isWiderThan } from "../utils/screen";

function RootLayout() {
  const courseMatch = useMatch("/courses/:courseId/*");
  const activeCourseId = courseMatch?.params.courseId ?? null;

  const fileUpload = useFileUpload(activeCourseId);
  const coursesState = useCourses();
  const creation = useCreateCourse();
  const [isChatOpen, setIsChatOpen] = useState(() => isWiderThan(1024));

  const navigate = useNavigate();

  async function handleCreateCourse(initialPrompt, files) {
    const created = await creation.createCourse(initialPrompt, files);
    if (created) {
      coursesState.addCourse(created);
      navigate(`/courses/${created.id}`);
    }
  }

  async function handleDeleteCourse(course) {
    const confirmed = window.confirm(
      `Delete course "${course.title}"? This cannot be undone.`,
    );
    if (!confirmed) return;

    const deleted = await coursesState.removeCourse(course.id);
    if (deleted && activeCourseId === course.id) navigate("/");
  }

  return (
    <div className="flex h-screen">
      <Sidebar
        courses={coursesState.courses}
        activeCourseId={activeCourseId}
        onSelectCourse={(courseId) => navigate(`/courses/${courseId}`)}
        onNewCourse={() => navigate("/")}
        onDeleteCourse={handleDeleteCourse}
        isLoading={coursesState.isLoading}
        error={coursesState.error}
        disabled={creation.isCreating}
      />

      <Outlet
        context={{
          fileUpload,
          isChatOpen,
          setIsChatOpen,
          creation,
          handleCreateCourse,
          refreshCourses: coursesState.refresh,
        }}
      />
    </div>
  );
}

export default RootLayout;
