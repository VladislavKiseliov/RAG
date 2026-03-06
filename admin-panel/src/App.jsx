import { RouterProvider } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { appRouter } from './router';

function App() {
  return (
    <>
      <RouterProvider router={appRouter} />
      <Toaster position="bottom-right" toastOptions={{ duration: 4000 }} />
    </>
  );
}

export default App;
