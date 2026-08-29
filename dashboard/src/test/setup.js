import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Vitest runs without injected globals, so testing-library's automatic
// cleanup never registers; unmount rendered components between tests
// explicitly to keep each test's DOM isolated.
afterEach(cleanup);
