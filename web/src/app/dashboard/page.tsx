"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DashboardRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/sala-de-comando"); }, [router]);
  return null;
}
