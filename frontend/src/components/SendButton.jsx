import { ArrowUp } from "lucide-react";

function SendButton({ onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="bg-accent hover:bg-accent/90 text-paper rounded-md p-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-accent"
    >
      <ArrowUp size={18} strokeWidth={2.5} />
    </button>
  );
}

export default SendButton;