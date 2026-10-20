import { useOutletContext } from "react-router";
import CoursePrompt from "../components/CoursePrompt";

function NewCoursePage() {
  const { creation, handleCreateCourse } = useOutletContext();

  return (
    <div className="flex-1 flex items-center justify-center px-4">
      <CoursePrompt
        onSubmit={handleCreateCourse}
        isLoading={creation.isCreating}
        error={creation.error}
      />
    </div>
  );
}

export default NewCoursePage;
