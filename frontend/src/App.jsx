import { Route, Routes } from "react-router";
import RootLayout from "./pages/RootLayout";
import NewCoursePage from "./pages/NewCoursePage";
import CourseLayout from "./pages/CourseLayout";
import TopicLayout from "./pages/TopicLayout";
import TheoryTab from "./pages/TheoryTab";
import TasksTab from "./pages/TasksTab";
import CourseView from "./components/CourseView";
import ReviewPage from "./pages/ReviewPage";

function App() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        <Route index element={<NewCoursePage />} />
        <Route path="courses/:courseId" element={<CourseLayout />}>
          <Route index element={<CourseView />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="topics/:topicId" element={<TopicLayout />}>
            <Route index element={<TheoryTab />} />
            <Route path="tasks" element={<TasksTab />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
