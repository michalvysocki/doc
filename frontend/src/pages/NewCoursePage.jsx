import { useOutletContext } from "react-router";
import CoursePrompt from "../components/CoursePrompt";

function NewCoursePage() {
  const { creation, handleCreateCourse } = useOutletContext();

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-20 px-4">
      <div className="text-center">
        <h1 className="text-7xl font-bold text-accent">Doc</h1>
        <p className="mt-4 text-xl text-ink">Your AI teaching assistant</p>
      </div>
      <CoursePrompt
        onSubmit={handleCreateCourse}
        isLoading={creation.isCreating}
        status={creation.status}
        error={creation.error}
      />
    </div>
  );
}

export default NewCoursePage;
