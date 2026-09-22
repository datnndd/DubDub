import React, { useEffect } from 'react';
import { useDubDubStore } from './store';
import { Header } from './components/Header';
import { WorkflowStepper } from './components/WorkflowStepper';
import { StatusFooter } from './components/StatusFooter';
import { ProjectDrawer } from './components/ProjectDrawer';
import { FloatingPill } from './components/FloatingPill';
import { Stage1Prepare } from './screens/Stage1Prepare';
import { Stage2ReviewTranscript } from './screens/Stage2ReviewTranscript';
import { Stage3VoiceDubbing } from './screens/Stage3VoiceDubbing';
import { Stage4EditVideo } from './screens/Stage4EditVideo';

export const App: React.FC = () => {
  const currentStep = useDubDubStore((s) => s.currentStep);
  const activeProjectId = useDubDubStore((s) => s.activeProjectId);
  const initializeBackend = useDubDubStore((s) => s.initializeBackend);
  const loadProjects = useDubDubStore((s) => s.loadProjects);
  const selectProject = useDubDubStore((s) => s.selectProject);
  const loadVoices = useDubDubStore((s) => s.loadVoices);

  useEffect(() => {
    initializeBackend();
    loadProjects();
    loadVoices();
    if (activeProjectId) {
      selectProject(activeProjectId);
    }
  }, []);

  const renderStage = () => {
    switch (currentStep) {
      case 1:
        return <Stage1Prepare />;
      case 2:
        return <Stage2ReviewTranscript />;
      case 3:
        return <Stage3VoiceDubbing />;
      case 4:
        return <Stage4EditVideo />;
      default:
        return <Stage1Prepare />;
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-[#F9F8F5] text-stone-800 font-sans antialiased select-none text-xs">
      <Header />
      <WorkflowStepper />
      <main className="flex-1 min-h-0 w-full overflow-hidden flex flex-col">
        {renderStage()}
      </main>
      <StatusFooter />
      <ProjectDrawer />
      <FloatingPill />
    </div>
  );
};
