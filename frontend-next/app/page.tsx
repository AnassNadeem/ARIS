import { AboutARIS } from "@/components/home/AboutARIS";
import { HeroSection } from "@/components/home/HeroSection";
import { HowItWorks } from "@/components/home/HowItWorks";

export default function HomePage() {
  return (
    <main className="flex-1 bg-carbon">
      <HeroSection />
      <HowItWorks />
      <AboutARIS />
    </main>
  );
}
