import { Route, Routes } from "react-router";
import RootLayout from "./pages/RootLayout";
import NewCoursePage from "./pages/NewCoursePage";
import CourseLayout from "./pages/CourseLayout";
import CourseView from "./components/CourseView";

function App() {
  return (
    <Routes>
      <Route element={<RootLayout />}>
        <Route index element={<NewCoursePage />} />
        <Route path="courses/:courseId" element={<CourseLayout />}>
          <Route index element={<CourseView />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
