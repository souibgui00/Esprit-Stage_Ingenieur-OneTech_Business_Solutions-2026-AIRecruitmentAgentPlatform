import './globals.css';
import { AuthProvider } from '../context/AuthContext';
export const metadata={title:'Next Role — your job-search workspace',description:'A personal AI job-search workspace'};
export default function RootLayout({children}){return <html lang="en"><body><AuthProvider>{children}</AuthProvider></body></html>}
