import { useState } from "react";
import {
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Trash2,
  UserRound,
} from "lucide-react";
import AboutMePanel from "./AboutMePanel";
import Skeleton from "./Skeleton";
import { isWiderThan } from "../utils/screen";

// Both states render the same <aside>, so React keeps the element and the width animates.
// Below md the open panel overlays the content; a spacer keeps the collapsed width in the layout.
const ASIDE =
  "shrink-0 overflow-hidden border-r border-line bg-card transition-[width] duration-200 ease-out motion-reduce:transition-none";

function Sidebar({
  courses,
  activeCourseId,
  onSelectCourse,
  onNewCourse,
  onDeleteCourse,
  isLoading,
  error,
  disabled,
}) {
  const [isOpen, setIsOpen] = useState(() => isWiderThan(768));
  const [isAboutOpen, setIsAboutOpen] = useState(false);

  // On narrow screens the overlay would cover the page the user just picked.
  function closeOnNarrow() {
    if (!isWiderThan(768)) setIsOpen(false);
  }

  const overlay = isOpen && (
    <>
      <div className="w-12 shrink-0 md:hidden" />
      <div
        className="fixed inset-0 z-20 bg-ink/20 md:hidden"
        onClick={() => setIsOpen(false)}
      />
    </>
  );

  if (!isOpen) {
    return (
      <>
        {overlay}
        <aside className={`w-12 ${ASIDE}`}>
          <div className="w-12 flex flex-col items-center gap-2 py-3">
            <button
              type="button"
              onClick={() => setIsOpen(true)}
              aria-label="Open sidebar"
              className="p-2 rounded-md text-muted hover:text-ink hover:bg-line"
            >
              <PanelLeftOpen size={18} />
            </button>
            <button
              type="button"
              onClick={onNewCourse}
              disabled={disabled}
              aria-label="New course"
              className="p-2 rounded-md text-muted hover:text-ink hover:bg-line disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Plus size={18} />
            </button>
            <button
              type="button"
              onClick={() => {
                setIsOpen(true);
                setIsAboutOpen(true);
              }}
              aria-label="About me"
              className="p-2 rounded-md text-muted hover:text-ink hover:bg-line"
            >
              <UserRound size={18} />
            </button>
          </div>
        </aside>
      </>
    );
  }

  return (
    <>
      {overlay}
      <aside
        className={`w-64 max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-30 ${ASIDE}`}
      >
        <div className="w-64 h-full flex flex-col">
          <div className="flex items-center justify-between px-3 py-3">
            <span className="text-xl font-bold text-accent">Doc</span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Close sidebar"
              className="p-2 rounded-md text-muted hover:text-ink hover:bg-line"
            >
              <PanelLeftClose size={18} />
            </button>
          </div>

          <div className="px-3">
            <button
              type="button"
              onClick={onNewCourse}
              disabled={disabled}
              className={`w-full flex items-center gap-2 rounded-md px-3 py-2 type-label disabled:opacity-40 disabled:cursor-not-allowed ${
                activeCourseId === null
                  ? "bg-accent/10 text-accent"
                  : "text-ink hover:bg-line"
              }`}
            >
              <Plus size={16} className="text-accent" />
              New course
            </button>
          </div>

          <p className="px-6 pt-4 type-caption uppercase tracking-wide text-faint">
            Courses
          </p>
          <nav className="flex-1 overflow-y-auto px-3 pb-3 pt-2 flex flex-col gap-1">
            {isLoading && <Skeleton lines={3} className="px-3 py-2" />}
            {error && <p className="type-caption text-warn px-3">{error}</p>}
            {!isLoading && !error && courses.length === 0 && (
              <p className="type-caption text-faint px-3">
                No courses yet. Create your first one above.
              </p>
            )}

            {courses.map((course) => (
              <div
                key={course.id}
                className={`group flex items-center rounded-md ${
                  course.id === activeCourseId
                    ? "bg-accent/10"
                    : "hover:bg-line"
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    onSelectCourse(course.id);
                    closeOnNarrow();
                  }}
                  disabled={disabled}
                  title={course.title}
                  className={`flex-1 min-w-0 text-left px-3 py-2 truncate disabled:opacity-40 disabled:cursor-not-allowed ${
                    course.id === activeCourseId
                      ? "type-label text-accent"
                      : "type-body text-ink"
                  }`}
                >
                  {course.title}
                </button>
                {course.reviews_due > 0 && (
                  <span
                    className="mr-1 rounded-full bg-accent px-1.5 type-caption text-paper"
                    title={`${course.reviews_due} tasks to review`}
                  >
                    {course.reviews_due}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => onDeleteCourse(course)}
                  disabled={disabled}
                  aria-label={`Delete ${course.title}`}
                  className="p-2 mr-1 rounded-md text-faint hover:text-warn hover:bg-line opacity-0 group-hover:opacity-100 focus:opacity-100 disabled:hidden"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </nav>

          <AboutMePanel
            isOpen={isAboutOpen}
            onToggle={() => setIsAboutOpen((prev) => !prev)}
          />
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
