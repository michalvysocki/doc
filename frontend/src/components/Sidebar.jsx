import { useState } from "react";
import { PanelLeftClose, PanelLeftOpen, Plus, Trash2 } from "lucide-react";

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
  const [isOpen, setIsOpen] = useState(true);

  if (!isOpen) {
    return (
      <aside className="w-12 shrink-0 border-r border-line flex flex-col items-center gap-2 py-3">
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          aria-label="Open sidebar"
          className="p-2 rounded-md text-ink/70 hover:bg-line/50"
        >
          <PanelLeftOpen size={18} />
        </button>
        <button
          type="button"
          onClick={onNewCourse}
          disabled={disabled}
          aria-label="New course"
          className="p-2 rounded-md text-ink/70 hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Plus size={18} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-64 shrink-0 border-r border-line flex flex-col">
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-sm font-semibold text-ink">Courses</span>
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          aria-label="Close sidebar"
          className="p-2 rounded-md text-ink/70 hover:bg-line/50"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="px-3">
        <button
          type="button"
          onClick={onNewCourse}
          disabled={disabled}
          className="w-full flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm text-ink hover:bg-line/50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Plus size={16} />
          New course
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 flex flex-col gap-1">
        {isLoading && <p className="text-xs text-ink/60 px-3">Loading...</p>}
        {error && <p className="text-xs text-warn px-3">{error}</p>}
        {!isLoading && !error && courses.length === 0 && (
          <p className="text-xs text-ink/60 px-3">No courses yet</p>
        )}

        {courses.map((course) => (
          <div
            key={course.id}
            className={`group flex items-center rounded-md ${
              course.id === activeCourseId ? "bg-accent/10" : "hover:bg-line/50"
            }`}
          >
            <button
              type="button"
              onClick={() => onSelectCourse(course.id)}
              disabled={disabled}
              title={course.title}
              className={`flex-1 min-w-0 text-left text-sm px-3 py-2 truncate disabled:opacity-40 disabled:cursor-not-allowed ${
                course.id === activeCourseId
                  ? "text-accent font-medium"
                  : "text-ink"
              }`}
            >
              {course.title}
            </button>
            {course.reviews_due > 0 && (
              <span
                className="mr-1 rounded-full bg-accent px-1.5 text-xs text-paper"
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
              className="p-2 mr-1 rounded-md text-ink/50 hover:text-warn opacity-0 group-hover:opacity-100 focus:opacity-100 disabled:hidden"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
