import * as React from "react"
import { Settings, Smile, Search, BookOpen, Home } from "lucide-react"

import {
    CommandDialog,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
    CommandSeparator,
    CommandShortcut,
} from "@/components/ui/command"
import { useChapterList } from '@/hooks/useChapterList'
import { useNavigate } from 'react-router-dom'
import { useSettings } from "@/stores/settingsStore"

export function CommandMenu() {
    const [open, setOpen] = React.useState(false)
    const navigate = useNavigate();
    const { data: chapterList } = useChapterList();
    const { setTheme } = useSettings();

    React.useEffect(() => {
        const down = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                setOpen((open) => !open)
            }
        }

        document.addEventListener("keydown", down)
        return () => document.removeEventListener("keydown", down)
    }, [])

    const runCommand = React.useCallback((command: () => unknown) => {
        setOpen(false)
        command()
    }, [])

    return (
        <CommandDialog open={open} onOpenChange={setOpen}>
            <CommandInput placeholder="Type a command or search..." />
            <CommandList>
                <CommandEmpty>No results found.</CommandEmpty>
                <CommandGroup heading="Suggestions">
                    <CommandItem onSelect={() => runCommand(() => navigate('/'))}>
                        <Home className="mr-2 h-4 w-4" />
                        <span>Home</span>
                    </CommandItem>
                    <CommandItem onSelect={() => runCommand(() => alert('Search not implemented'))}>
                        <Search className="mr-2 h-4 w-4" />
                        <span>Search Content</span>
                        <CommandShortcut>⌘S</CommandShortcut>
                    </CommandItem>
                </CommandGroup>

                <CommandSeparator />

                <CommandGroup heading="Chapters">
                    {chapterList?.chapters.map((chapter) => (
                        <CommandItem
                            key={chapter.id}
                            onSelect={() => runCommand(() => navigate(`/chapter/${chapter.id}`))}
                        >
                            <BookOpen className="mr-2 h-4 w-4" />
                            <span>{chapter.title}</span>
                            <CommandShortcut>#{chapter.chapter_index}</CommandShortcut>
                        </CommandItem>
                    ))}
                </CommandGroup>

                <CommandSeparator />

                <CommandGroup heading="Settings">
                    <CommandItem onSelect={() => runCommand(() => setTheme("light"))}>
                        <Smile className="mr-2 h-4 w-4" />
                        <span>Light Mode</span>
                    </CommandItem>
                    <CommandItem onSelect={() => runCommand(() => setTheme("dark"))}>
                        <Settings className="mr-2 h-4 w-4" />
                        <span>Dark Mode</span>
                    </CommandItem>
                </CommandGroup>
            </CommandList>
        </CommandDialog>
    )
}
