import { useOutletContext } from "react-router";
import TopicCard from "./TopicCard";

function CourseView() {
  const { course } = useOutletContext();

  return (
    <div className="max-w-3xl mx-auto w-full">
      <h1 className="text-xl font-semibold text-ink">{course.title}</h1>
      <div className="flex flex-col gap-2 mt-4">
        {course.topics.map((topic) => (
          <TopicCard key={topic.id} topic={topic} />
        ))}
      </div>
    </div>
  );
}

export default CourseView;
