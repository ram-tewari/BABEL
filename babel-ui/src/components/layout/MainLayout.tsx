import { CommandMenu } from '@/components/search/CommandMenu';
import { useSettings } from '@/stores/settingsStore';
import { Sidebar, Header } from '@/components/layout';

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const { toggleSidebar } = useSettings();

  return (
    <div className="main-layout bg-[var(--bg-primary)] h-screen w-full flex overflow-hidden">
      <CommandMenu />

      {/* Sidebar (Fixed/Static based on screen size) */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative transition-all duration-300 ease-in-out">
        <Header onToggleSidebar={toggleSidebar} />

        <main className="flex-1 overflow-y-auto scroll-smooth px-2 md:px-0 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          <div className="max-w-5xl mx-auto py-8 px-4 md:px-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
