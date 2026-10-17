import useFileUpload from "./hooks/useFileUpload";
import useChat from "./hooks/useChat";
import MessageHistory from "./components/MessageHistory";
import MessageComposer from "./components/MessageComposer";

function App() {
  const fileUpload = useFileUpload();
  const chat = useChat(fileUpload);

  return (
    <div className="flex flex-col h-screen">
      <MessageHistory
        messageHistory={chat.messageHistory}
        isLoading={chat.isLoading}
      />
      <div className="pb-4 px-4">
        <MessageComposer chat={chat} fileUpload={fileUpload} />
      </div>
    </div>
  );
}

export default App;
