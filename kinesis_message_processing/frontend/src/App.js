import { ChakraProvider, extendTheme } from '@chakra-ui/react';
import { Dashboard } from './components/Dashboard';

const theme = extendTheme({
  config: {
    initialColorMode: 'light',
    useSystemColorMode: false,
  },
});

function App() {
  return (
    <ChakraProvider theme={theme}>
      <Dashboard />
    </ChakraProvider>
  );
}

export default App;