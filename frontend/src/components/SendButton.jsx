import { ArrowUp } from "lucide-react";

function SendButton({ onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} className="btn-primary p-3">
      <ArrowUp size={18} strokeWidth={2.5} />
    </button>
  );
}

export default SendButton;
