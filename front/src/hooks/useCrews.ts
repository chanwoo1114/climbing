import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from '@tanstack/react-query'

import { updateMe, type Me } from '@/api/auth'
import {
  createCrew,
  deleteCrew,
  fetchCrew,
  fetchCrewFeed,
  fetchCrewMembers,
  fetchCrewRecruitments,
  fetchCrews,
  joinCrew,
  kickCrewMember,
  leaveCrew,
  setCrewMemberRole,
  setCrewMemberStatus,
  updateCrew,
  type Crew,
  type CrewInput,
  type CrewListParams,
  type CrewMemberStatus,
  type CrewSummary,
  type CrewUpdate,
  isActiveStatus,
} from '@/api/crews'
import type { CursorPage } from '@/api/gyms'

/**
 * 쿼리 키
 * - ['crews', 'list', params]              목록 (무한) — q/gym 별
 * - ['crews', id]                          상세
 * - ['crews', id, 'members', status]       크루원 (무한) — active / pending
 * - ['feed', 'crew', id]                   크루 피드 (무한) — 'feed' 접두사라 useClimbs 의 좋아요 반영 대상
 * - ['posts', 'list', { crew: id }]        크루 주최 모집글 (무한) — usePosts 의 댓글 수 반영·무효화 대상
 * ['crews', id] 무효화에 크루원 목록이 같이 딸려간다.
 */
const listKey = (params: CrewListParams) => ['crews', 'list', params] as const
const crewKey = (id: number) => ['crews', id] as const
const membersKey = (id: number, status: CrewMemberStatus) =>
  ['crews', id, 'members', status] as const
const feedKey = (id: number) => ['feed', 'crew', id] as const
const recruitmentsKey = (id: number) => ['posts', 'list', { crew: id }] as const

/** 목록 캐시 전부 (q/gym 조합 무관) */
const CREW_LISTS = { queryKey: ['crews', 'list'] }

type CrewPages = InfiniteData<CursorPage<CrewSummary>, string | undefined>

/** 같은 크루가 목록·상세 캐시에 동시에 있을 수 있어 my_status·member_count 는 둘 다 고친다 */
function patchCrewEverywhere(
  queryClient: QueryClient,
  id: number,
  patch: <T extends CrewSummary>(crew: T) => T,
) {
  queryClient.setQueriesData<CrewPages>(
    CREW_LISTS,
    (pages) =>
      pages && {
        ...pages,
        pages: pages.pages.map((page) => ({
          ...page,
          results: page.results.map((crew) => (crew.id === id ? patch(crew) : crew)),
        })),
      },
  )
  queryClient.setQueryData<Crew>(crewKey(id), (crew) => crew && patch(crew))
}

const cursorPaging = {
  initialPageParam: undefined as string | undefined,
  getNextPageParam: <T>(lastPage: CursorPage<T>) => lastPage.nextCursor ?? undefined,
}

// --- 조회 ---

export function useCrews(params: CrewListParams = {}) {
  return useInfiniteQuery({
    queryKey: listKey(params),
    queryFn: ({ pageParam }) => fetchCrews(params, pageParam),
    ...cursorPaging,
  })
}

export function useCrew(id: number) {
  return useQuery({
    queryKey: crewKey(id),
    queryFn: () => fetchCrew(id),
    enabled: Number.isFinite(id),
  })
}

/** pending 은 크루장·운영진만 볼 수 있으니 호출부가 enabled 로 막는다 */
export function useCrewMembers(id: number, status: CrewMemberStatus = 'active', enabled = true) {
  return useInfiniteQuery({
    queryKey: membersKey(id, status),
    queryFn: ({ pageParam }) => fetchCrewMembers(id, status, pageParam),
    enabled: enabled && Number.isFinite(id),
    ...cursorPaging,
  })
}

/** 크루원이 아니고 비공개 피드면 403(permission_denied) — 재시도해도 같으니 바로 끝낸다 */
export function useCrewFeed(id: number) {
  return useInfiniteQuery({
    queryKey: feedKey(id),
    queryFn: ({ pageParam }) => fetchCrewFeed(id, pageParam),
    enabled: Number.isFinite(id),
    retry: false,
    ...cursorPaging,
  })
}

export function useCrewRecruitments(id: number) {
  return useInfiniteQuery({
    queryKey: recruitmentsKey(id),
    queryFn: ({ pageParam }) => fetchCrewRecruitments(id, pageParam),
    enabled: Number.isFinite(id),
    ...cursorPaging,
  })
}

// --- 크루 CRUD ---

export function useCreateCrew() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CrewInput) => createCrew(input),
    onSuccess: (crew) => {
      // 상세로 바로 이동하므로 응답을 캐시에 미리 넣어 두면 로딩 없이 뜬다
      queryClient.setQueryData(crewKey(crew.id), crew)
      queryClient.invalidateQueries(CREW_LISTS)
    },
  })
}

export function useUpdateCrew(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CrewUpdate) => updateCrew(id, input),
    onSuccess: (crew) => {
      queryClient.setQueryData(crewKey(crew.id), crew)
      queryClient.invalidateQueries(CREW_LISTS)
      // 이름이 바뀌면 프로필의 대표 크루 표시도 따라가야 한다
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

export function useDeleteCrew() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteCrew(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: crewKey(id) })
      queryClient.removeQueries({ queryKey: feedKey(id) })
      queryClient.removeQueries({ queryKey: recruitmentsKey(id) })
      queryClient.invalidateQueries(CREW_LISTS)
      // 서버가 이 크루를 대표 크루로 둔 회원의 참조를 비운다
      queryClient.invalidateQueries({ queryKey: ['me'] })
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

// --- 가입 / 탈퇴 ---

/**
 * 가입 — 응답의 status 로 즉시 가입(active → member)인지 승인 대기(pending)인지 알 수 있어
 * 목록·상세의 my_status·member_count 를 바로 고친다. chat_room_id 는 상세를 다시 받아야 온다.
 */
export function useJoinCrew(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => joinCrew(id),
    onSuccess: (member) => {
      const active = member.status === 'active'
      patchCrewEverywhere(queryClient, id, (crew) => ({
        ...crew,
        myStatus: active ? 'member' : 'pending',
        memberCount: active ? crew.memberCount + 1 : crew.memberCount,
      }))
      queryClient.invalidateQueries({ queryKey: crewKey(id) })
      // 피드는 크루원이 되면서 볼 수 있게 됐을 수 있다 (403 → 목록)
      if (active) queryClient.invalidateQueries({ queryKey: feedKey(id) })
    },
  })
}

/** 탈퇴(활동 중) 또는 신청 취소(승인 대기). 대표 크루였다면 서버가 비운다 */
export function useLeaveCrew(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => leaveCrew(id),
    onSuccess: () => {
      patchCrewEverywhere(queryClient, id, (crew) => ({
        ...crew,
        myStatus: null,
        memberCount: isActiveStatus(crew.myStatus)
          ? Math.max(0, crew.memberCount - 1)
          : crew.memberCount,
      }))
      queryClient.invalidateQueries({ queryKey: crewKey(id) })
      queryClient.invalidateQueries({ queryKey: feedKey(id), refetchType: 'none' })
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
}

// --- 크루원 관리 (크루장·운영진) ---

/** 승인은 member_count 가, 거절은 대기 목록만 바뀐다 — 상세(+크루원)와 목록을 다시 받는다 */
export function useSetCrewMemberStatus(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, status }: { userId: number; status: 'active' | 'rejected' }) =>
      setCrewMemberStatus(id, userId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: crewKey(id) })
      queryClient.invalidateQueries(CREW_LISTS)
    },
  })
}

export function useSetCrewMemberRole(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: 'staff' | 'member' }) =>
      setCrewMemberRole(id, userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membersKey(id, 'active') }),
  })
}

export function useKickCrewMember(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: number) => kickCrewMember(id, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: crewKey(id) })
      queryClient.invalidateQueries(CREW_LISTS)
      queryClient.invalidateQueries({ queryKey: feedKey(id), refetchType: 'none' })
    },
  })
}

// --- 대표 크루 ---

/** PATCH /users/me/ { main_crew } — 내가 활동 중인 크루만. null 이면 해제 */
export function useSetMainCrew() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (crewId: number | null) => updateMe({ mainCrew: crewId }),
    onSuccess: (me) => {
      queryClient.setQueryData<Me>(['me'], me)
      // 공개 프로필(UserProfile)의 대표 크루 칩도 따라간다
      queryClient.invalidateQueries({ queryKey: ['users', me.id], exact: true })
    },
  })
}
