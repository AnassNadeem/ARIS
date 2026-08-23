import { AboutARIS } from "@/components/home/AboutARIS";
import { HeroSection } from "@/components/home/HeroSection";
import { HowItWorks } from "@/components/home/HowItWorks";
import { AppHeader } from "@/components/layout/AppHeader";

export default function HomePage() {
  return (
    <>
      <AppHeader />
      <main className="flex-1 bg-carbon">
        <HeroSection />
        <HowItWorks />
        <AboutARIS />
      </main>
    </>
  );
}
